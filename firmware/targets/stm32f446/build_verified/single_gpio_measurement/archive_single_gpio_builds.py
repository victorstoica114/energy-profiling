"""Archive the three already-built single-GPIO images without running firmware."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str]) -> str:
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    return result.stdout


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def elf_bytes(blob: bytes, address: int, count: int) -> bytes:
    if blob[:6] != b"\x7fELF\x01\x01":
        raise ValueError("Expected a little-endian ELF32 image")
    section_offset = struct.unpack_from("<I", blob, 32)[0]
    entry_size, section_count = struct.unpack_from("<HH", blob, 46)
    for index in range(section_count):
        section = struct.unpack_from("<10I", blob, section_offset + index * entry_size)
        if section[1] != 8 and section[3] <= address and address + count <= section[3] + section[5]:
            start = section[4] + address - section[3]
            return blob[start:start + count]
    raise ValueError(f"No file-backed section covers {address:x}+{count}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--temp", type=Path, required=True)
    parser.add_argument("--packages", type=Path, required=True)
    parser.add_argument("--target", choices=("esp32", "rp2040", "stm32f446"), action="append")
    args = parser.parse_args()
    project = args.project.resolve()
    manifest = json.loads((project / "config/experiment.json").read_text())
    for target in args.target or ("esp32", "rp2040", "stm32f446"):
        target_dir = project / "firmware/targets" / target
        build = args.temp / ("energy-v3-" + target)
        archive = target_dir / "build_verified/single_gpio_measurement"
        if (archive / "verification.json").exists():
            raise FileExistsError("Refusing to replace a completed verification archive: " + str(archive))
        archive.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(__file__), archive / "archive_single_gpio_builds.py")
        shutil.copy2(Path(__file__).with_name("single_gpio_native_commands.json"), archive / "native_commands.json")
        tool_dir = args.packages / ("toolchain-xtensa-esp-elf" if target == "esp32" else "toolchain-gccarmnoneeabi") / "bin"
        triple = "xtensa-esp-elf" if target == "esp32" else "arm-none-eabi"
        compiler = tool_dir / (triple + "-gcc.exe")
        objdump = tool_dir / (triple + "-objdump.exe")
        nm = tool_dir / (triple + "-nm.exe")
        stem = "energy_bench_" + target
        elf = build / (stem + ".elf")
        if not elf.is_file():
            raise FileNotFoundError(elf)
        artifact_names = [stem + suffix for suffix in (".elf", ".bin", ".map")]
        if target == "rp2040":
            artifact_names[-1] = stem + ".elf.map"
        if target == "esp32":
            artifact_names += ["bootloader/bootloader.bin", "partition_table/partition-table.bin"]
        elif target == "rp2040":
            artifact_names += [stem + ".uf2", stem + ".hex"]
        else:
            artifact_names += [stem + ".hex"]
        artifact_hashes = {}
        for name in artifact_names:
            dest = archive / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(build / name, dest)
            artifact_hashes[name] = sha(dest)
        for name in ("compile_commands.json", "native_build.log", "native_incremental_build.log"):
            if (build / name).is_file():
                shutil.copy2(build / name, archive / name)
        if (target_dir / "sdk.lock.json").exists():
            shutil.copy2(target_dir / "sdk.lock.json", archive / "sdk.lock.json")
        else:
            shutil.copy2(args.packages / "framework-espidf/package.json", archive / "sdk_package.json")
            shutil.copy2(args.packages / "toolchain-xtensa-esp-elf/package.json", archive / "compiler_package.json")
        if target == "esp32":
            shutil.copy2(target_dir / "sdkconfig", archive / "sdkconfig")
            shutil.copy2(build / "toolchain/cflags", archive / "toolchain_cflags.txt")
            write_json(archive / "flash_manifest.json", {
                "hardware_flashed": False,
                "flash_mode": "dio", "flash_frequency_mhz": 40, "flash_capacity_mib": 4,
                "files": {
                    "0x1000": "bootloader/bootloader.bin",
                    "0x8000": "partition_table/partition-table.bin",
                    "0x10000": stem + ".bin",
                },
            })
        commands = json.loads((build / "compile_commands.json").read_text())
        sdk_sources = {}
        for command in commands:
            source = Path(command["file"]).resolve()
            if source.is_file() and not source.is_relative_to(project):
                sdk_sources[str(source)] = sha(source)
        write_json(archive / "external_compiled_source_sha256.json", sdk_sources)
        source_paths = set()
        common_paths = (project / "firmware/common").rglob("*")
        for path in common_paths:
            if path.is_file() and path.suffix in (".c", ".h", ".cmake"):
                source_paths.add(path)
        for path in target_dir.rglob("*"):
            if path.is_file() and "build_verified" not in path.parts and (
                path.suffix.lower() in (".c", ".h", ".s", ".ld", ".cmake")
                or path.name in ("CMakeLists.txt", "sdkconfig", "sdkconfig.defaults", "sdk.lock.json")
            ):
                source_paths.add(path)
        for name in ("config/experiment.json", "data/manifest.json", "data/compression.bin", "data/crypto.bin", "data/dsp.bin", "tools/generate_inputs.py"):
            source_paths.add(project / name)
        source_hashes = {p.relative_to(project).as_posix(): sha(p) for p in sorted(source_paths)}
        write_json(archive / "source_sha256_at_archive.json", source_hashes)
        common_names = {"bench_runner.c", "bench_data.c", "bench_algorithms.c", "bench_kernels.c"}
        benchmark_commands = [x for x in commands if Path(x["file"]).name in common_names]
        if len(benchmark_commands) != 4:
            raise ValueError(f"Expected exactly four common compilation commands: {target}")
        flag_evidence = {}
        for command in benchmark_commands:
            flags = re.findall(r"-O\S+|-std=\S+|-fno-lto|-fno-fast-math|-ffp-contract=\S+|-m(?:cpu|fpu|float-abi)=\S+", command["command"])
            optimization = [f for f in flags if f.startswith("-O")]
            if not optimization or optimization[-1] != "-O2":
                raise ValueError(f"Common file is not O2: {command}")
            if not {"-fno-lto", "-fno-fast-math", "-ffp-contract=off"}.issubset(flags):
                raise ValueError(f"Missing numeric/build flags: {command}")
            flag_evidence[Path(command["file"]).name] = flags
        write_json(archive / "benchmark_compile_commands.json", benchmark_commands)
        symbols = run([str(nm), "-S", "--size-sort", str(elf)])
        (archive / "symbols.txt").write_text(symbols, encoding="utf-8")
        disassembly = run([str(objdump), "-d", str(elf)])
        blocks = re.split(r"(?=^[0-9a-f]+ <[^>]+>:$)", disassembly, flags=re.M)
        selected = [b for b in blocks if re.match(r"^[0-9a-f]+ <(?:bench_main|bench_platform_marker|bench_platform_init|bench_platform_wait_ms|bench_kernel_run|fail|fault_stop)(?:\.[^>]*)?>:$", b.splitlines()[0] if b.splitlines() else "")]
        selected_text = "\n".join(selected)
        if target == "esp32":
            # Linear Xtensa decoding can lose alignment across padding. Re-decode
            # each in-function branch target that is not a decoded instruction.
            main_block = next(b for b in selected if "<bench_main>:" in b.splitlines()[0])
            decoded_addresses = set(re.findall(r"^([0-9a-f]+):", main_block, re.M))
            branch_targets = set(re.findall(r"\b(?:beq|bne|beqz|bnez|j)\S*\s[^\n]*?\b([0-9a-f]{8}) <bench_main\+", main_block))
            for address in sorted(branch_targets - decoded_addresses):
                selected_text += "\nResynchronized branch target " + address + ":\n"
                selected_text += run([str(objdump), "-d", "--start-address=0x" + address,
                    "--stop-address=" + hex(int(address, 16) + 64), str(elf)])
        (archive / "disassembly_benchmark.txt").write_text(selected_text, encoding="utf-8")
        required_symbols = ("bench_main", "bench_platform_marker", "bench_kernel_run",
            "my_rle_encode", "my_delta_encode", "my_lz77_encode", "my_huffman_encode",
            "my_aes_encrypt", "my_sha256_hash", "my_chacha20_encrypt", "my_crc32",
            "my_fft", "my_fir_filter", "my_iir_filter", "my_dct")
        checks = {name + "_present": bool(re.search(r"\b" + name + r"$", symbols, re.M)) for name in required_symbols}
        checks["obsolete_signals_symbol_present"] = "bench_platform_signals" in symbols
        checks["report_symbol_present"] = bool(re.search(r"\bbench_platform_report$", symbols, re.M))
        checks["BENCH_event_literal_present"] = b"BENCH event=" in elf.read_bytes()
        checks["single_marker_disassembly_extracted"] = any("<bench_platform_marker>:" in b for b in selected)
        if not all(checks[name + "_present"] for name in required_symbols):
            raise ValueError(f"Missing benchmark symbols: {checks}")
        if any(checks[k] for k in ("obsolete_signals_symbol_present", "report_symbol_present", "BENCH_event_literal_present")):
            raise ValueError(f"Unexpected legacy or diagnostic content: {checks}")
        blob = elf.read_bytes()
        def symbol_bytes(name: str, length: int) -> bytes:
            matches = re.findall(r"^([0-9a-f]+) ([0-9a-f]+) \w " + re.escape(name) + r"$", symbols, re.M)
            if len(matches) != 1 or int(matches[0][1], 16) != length:
                raise ValueError(f"Expected unique sized symbol {name}: {matches}")
            return elf_bytes(blob, int(matches[0][0], 16), length)
        iterations = list(struct.unpack("<12I", symbol_bytes("bench_iterations", 48)))
        board_key = "stm32" if target == "stm32f446" else target
        expected_iterations = [manifest["boards"][board_key]["iterations"][a["name"]] for a in manifest["algorithms"]]
        if iterations != expected_iterations:
            raise ValueError(f"ELF repetition constants differ from manifest: {target}")
        input_hashes = {}
        for dataset in ("compression", "crypto", "dsp"):
            value = symbol_bytes("bench_" + dataset + "_input", 2048)
            if value != (project / "data" / (dataset + ".bin")).read_bytes():
                raise ValueError(f"ELF input differs from manifest data: {target}/{dataset}")
            input_hashes[dataset] = hashlib.sha256(value).hexdigest()
        checks["elf_iterations_match_manifest"] = True
        checks["elf_inputs_match_frozen_data"] = True
        marker_notes = {
            "esp32": "GPIO base0x3ff44000; mask0x40000; HIGH writes offset8(W1TS), LOW writes offset12(W1TC); memw barriers; HIGH path has no clear write.",
            "rp2040": "SIO base0xd0000000; mask4; HIGH writes offset20(GPIO_OUT_SET), LOW writes offset24(GPIO_OUT_CLR); dmb barriers; HIGH path has no clear write.",
            "stm32f446": "GPIOC base0x40020800; one write to BSRR offset24; HIGH value1, LOW value0x10000; dmb barriers. fault_stop inlines the HIGH-only BSRR write.",
        }
        record = {
            "schema": 1,
            "target": target,
            "profile": "single_gpio_measurement",
            "campaign": manifest.get("experiment_id", manifest.get("campaign_id", manifest.get("name"))),
            "archive_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "native_build_directory": str(build),
            "native_compile_and_link_passed": True,
            "build_exit_code": 0,
            "hardware_flashed": False,
            "hardware_execution_validated": False,
            "diagnostics_enabled": False,
            "marker_gpio": {"esp32": "GPIO18", "rp2040": "GPIO2", "stm32f446": "PC0"}[target],
            "source_snapshot_note": "Project source/header/config/input hashes observed after the successful final build. Documentation is excluded. No earlier archive was changed.",
            "manifest_sha256_at_archive": sha(project / "config/experiment.json"),
            "compiler": run([str(compiler), "--version"]).splitlines()[0],
            "compiler_executable_sha256": sha(compiler),
            "sdk_identity_evidence": "sdk.lock.json" if (target_dir / "sdk.lock.json").exists() else "sdk_package.json and CMake exact version guard 5.5.4",
            "sdk_lock_sha256": sha(target_dir / "sdk.lock.json") if (target_dir / "sdk.lock.json").exists() else None,
            "artifact_sha256": artifact_hashes,
            "common_compile_flags": flag_evidence,
            "static_checks": checks,
            "elf_iteration_constants": iterations,
            "elf_input_sha256": input_hashes,
            "marker_disassembly_review": marker_notes[target],
            "loop_disassembly_review": "bench_main loads the immutable repetition table, calls bench_kernel_run in a counted loop, and reaches marker(false) only through the successful batch path. Kernel failure writes marker(true) and finishes without a preliminary marker(false).",
            "verification_limits": [
                "Native build and static binary inspection only; no new firmware was flashed or executed on hardware.",
                "Single GPIO carries batch boundaries; workload identity follows manifest order and is not transmitted electrically.",
                "Physical oscillator frequency, supply isolation, marker waveform and PPK2 captures are not validated by compilation.",
            ],
        }
        write_json(archive / "verification.json", record)
        print(target, "archived", artifact_hashes[stem + ".bin"], len(source_hashes), "source hashes")


if __name__ == "__main__":
    main()
