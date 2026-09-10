/* Derived from the recovered Noela Pirleci benchmark library.
 * Repairs are recorded in this project's tests/kernel_tests/README.md.
 * This file intentionally preserves the original scalar algorithms.
 */
#include "bench_original_private.h"

static float fft_real_workspace[2048];
static float fft_imag_workspace[2048];

// COMPRESSION ALGORITHMS


int my_rle_encode(const uint8_t *input, int input_len, uint8_t *output) {
    if (input_len == 0) {
        return 0;
    }
    int out_idx = 0;
    for (int i = 0; i < input_len; i++) {
        uint8_t count = 1;
        
        /* Count equal consecutive bytes until the input ends, the byte changes, or the count reaches 255. */



        while (i + 1 < input_len && input[i] == input[i + 1] && count < 255) {
            count++;
            i++;
        }
        
        /* Write the current count/value pair. */
        output[out_idx++] = count;
        output[out_idx++] = input[i];
    }
    
    /* Return the encoded output length. */
    return out_idx;
}


int my_delta_encode(const uint8_t *input, int input_len, uint8_t *output) {

    if (input_len == 0) {
        return 0;
    }

    /* Copy the first input value unchanged. */
    output[0] = input[0];

    /* Write differences between consecutive input values, modulo 256. */

    for (int i = 1; i < input_len; i++ ) {
        output[i] = input[i] - input[i - 1];
    }

    /* Return the output length. */
    return input_len; 
}


int my_lz77_encode(const uint8_t *input, int input_len, uint8_t *output) {

    int out_idx = 0;
    int cursor = 0;

    while (cursor < input_len) {

        int max_match_len = 0;
        int max_match_dist = 0;
        int history_limit_start;

        /* Limit the backward history search to the configured window. */

        if (cursor < MAX_WINDOW_SIZE_LZ77) {
            history_limit_start = 0;
        } else {
            history_limit_start = cursor - MAX_WINDOW_SIZE_LZ77;
        }

        /* Find the longest match in the history window. */
        for (int i = history_limit_start; i < cursor; i++) {
            int current_match_len = 0;
            /* Extend the match while inside the lookahead and input bounds and while bytes match. */



            while ((current_match_len < MAX_LOOKAHEAD_SIZE_LZ77) &&
                   (cursor + current_match_len < input_len) &&
                   (input[i + current_match_len] == input[cursor + current_match_len])) {
                current_match_len++;
            }

            /* Replace the best match only when a strictly longer match is found, and update its distance. */


            if (current_match_len > max_match_len) {
                max_match_len = current_match_len;
                max_match_dist = cursor - i;
            }
        }

        /* Read the next literal only if the match does not reach the end. */
        uint8_t next_char = 0;
        if (cursor + max_match_len < input_len) {
            next_char = input[cursor + max_match_len];
        }

        /* Write distance, match length, and the optional literal. */
        output[out_idx++] = (uint8_t)max_match_dist;
        output[out_idx++] = (uint8_t)max_match_len;
        if (cursor + max_match_len < input_len) {
            output[out_idx++] = next_char;
        }

        /* Advance past the matched bytes and optional literal. */
        cursor += max_match_len;
        if (cursor < input_len) ++cursor;
    }

    /* Return the encoded output length. */
    return out_idx;
}

static minheap_element extract_min_node(TreelessEnv *env) {

    uint32_t min_freq = 0xFFFFFFFF;
    int min_idx = -1;

    /* Find the node with minimum frequency. */
    for (int i = 0; i < env->heap_size; i++) {
        if (env->heap[i].freq < min_freq ||
            (min_idx >= 0 && env->heap[i].freq == min_freq &&
             env->heap[i].branch_id < env->heap[min_idx].branch_id)) {
            min_freq = env->heap[i].freq;
            min_idx = i;
        }
    }

    /* Extract the minimum-frequency node. */
    minheap_element min_node = env->heap[min_idx];

    /* Replace the extracted node with the last entry and reduce the active pool size. */
    env->heap[min_idx] = env->heap[env->heap_size - 1];
    env->heap_size--;

    /* Return the extracted minimum-frequency node. */
    return min_node;
}

static void insert_node_in_minheap(TreelessEnv *env, minheap_element node) {

    /* Append a node to the minimum-extraction pool. */
    env->heap[env->heap_size] = node;
    env->heap_size++;
}

static void sort_codes_by_length(TreelessEnv *env, uint8_t *elements, int num_elements) {

    /* Sort by code length, then by symbol value for equal lengths. */
    for (int i = 0; i < num_elements - 1; i++) {
        for (int j = i + 1; j < num_elements; j++) {
            
            // Select the current entries for comparison.
            uint8_t elem_first = elements[i];
            uint8_t elem_second = elements[j];

            if ((env->lengths[elem_first] > env->lengths[elem_second]) || 
                (env->lengths[elem_first] == env->lengths[elem_second] && elem_first > elem_second)) {
                elements[i] = elem_second;
                elements[j] = elem_first;
            }
        }
    }
}

int my_huffman_encode(const uint8_t *input, int input_len, uint8_t *output) {

    if (!input || input_len < 0 || input_len > 2048 || !output) return -1;

    /* Complete canonical-code frame; header and payload are both in RUN. */
    memset(output, 0, 264);
    for (int b = 0; b < 4; ++b) output[b] = (uint8_t)((uint32_t)input_len >> (8*b));
    if (input_len == 0) return 264;

    // Use reusable static storage instead of allocating the environment with calloc.
    // The shared environment makes this function non-reentrant.
    static TreelessEnv env_static; 
    TreelessEnv *env = &env_static;
    memset(env, 0, sizeof(TreelessEnv)); // Reset the environment for each independent invocation.

    /* Count each input symbol. */
    uint32_t freqs[256] = {0};
    for (int i = 0; i < input_len; i++) {
        freqs[input[i]]++;
    }

    /* Insert one leaf node per present symbol, with its frequency. */
    for (int i = 0; i < 256; i++) {
        if (freqs[i] > 0) {
            minheap_element new_node = {freqs[i], (uint16_t)i}; // A leaf branch ID is the symbol value.
            insert_node_in_minheap(env, new_node);
            env->is_active[i] = 1;                              // Mark the symbol as present.
            env->branch_ids[i] = (uint16_t)i;                   // Initially each symbol belongs to its own branch.
        }
    }

    uint16_t next_branch_id = 256;   // Internal-node IDs start at 256.

    /* Construct Huffman code lengths by merging branches. */
    while (env->heap_size > 1) {
        // Extract the two minimum-frequency nodes.
        minheap_element min1 = extract_min_node(env);
        minheap_element min2 = extract_min_node(env);

        // Create an internal node with the sum of both frequencies.
        minheap_element new_node;
        new_node.freq = min1.freq + min2.freq;
        new_node.branch_id = next_branch_id++; // Assign a unique internal-node ID.

        // Insert the new internal node.
        insert_node_in_minheap(env, new_node);

        // Update branch membership for symbols in both merged branches.
        // Check each active symbol for membership in either extracted branch.
        // Move matching symbols to the new internal branch.
        for (int i = 0; i < 256; i++) {
            if (env->is_active[i]) {
                if (env->branch_ids[i] == min1.branch_id || env->branch_ids[i] == min2.branch_id) {
                    env->branch_ids[i] = new_node.branch_id;
                    env->lengths[i]++;
                }
            }
        }
    }

    /* Sort the active symbols for canonical code assignment. */
    uint8_t sorted_elements[256];
    int num_active_elements = 0;
    for (int i = 0; i < 256; i++) {
        if (env->is_active[i]) {
            sorted_elements[num_active_elements++] = (uint8_t)i;
        }
    }

    if (num_active_elements == 1) env->lengths[sorted_elements[0]] = 1;
    sort_codes_by_length(env, sorted_elements, num_active_elements);
    for (int i = 0; i < num_active_elements; ++i) {
        if (env->lengths[sorted_elements[i]] > 32) return -1;
    }
    memcpy(output + 8, env->lengths, 256);

    uint32_t current_code = 0;
    uint8_t current_length = env->lengths[sorted_elements[0]];

    for (int i = 0; i < num_active_elements; i++) {
        uint8_t elem = sorted_elements[i];

        // Left-shift the current code when its length increases.
        while (current_length < env->lengths[elem]) {
            current_code <<= 1;
            current_length++;
        }
        
        env->codes[elem].code = current_code;
        env->codes[elem].len = current_length;
        
        current_code++; // Advance to the next code of this length.
    }


    /* Encode the payload bits. */
    uint32_t payload_bits = 0;
    for (int i = 0; i < input_len; ++i) payload_bits += env->codes[input[i]].len;
    for (int b = 0; b < 4; ++b) output[4+b] = (uint8_t)(payload_bits >> (8*b));
    output += 264;
    int out_byte_idx = 0;
    int out_bit_idx = 0;
    output[0] = 0; // Initialize the first payload byte.

    for (int i = 0; i < input_len; i++) {

        uint8_t elem = input[i];
        canonical_code code_info = env->codes[elem];

        for (int bit_pos = code_info.len - 1; bit_pos >= 0; bit_pos--) {
            uint8_t bit = (code_info.code >> bit_pos) & 1;

            // Set the current output bit.
            output[out_byte_idx] |= (bit << (7 - out_bit_idx));
            out_bit_idx++;

            // Advance after filling a byte.
            if (out_bit_idx == 8) {
                out_bit_idx = 0;
                out_byte_idx++;
                if ((uint32_t)out_byte_idx * 8u < payload_bits) output[out_byte_idx] = 0;
            }
        }
    }

    /* Return the complete encoded frame length. */
    int total_bytes = out_byte_idx + (out_bit_idx > 0 ? 1 : 0);
    return 264 + total_bytes;
}



// CRYPTOGRAPHY AND DATA INTEGRITY ALGORITHMS


static uint8_t xtime(uint8_t x) {
    return (x << 1) ^ (((x >> 7) & 1) * 0x1b);
}

static void sub_bytes_step(uint8_t *state) {

    for (int i = 0; i < 16; i++) {
        state[i] = sbox[state[i]];
    }
}

static void shift_rows_step(uint8_t *state) {

    uint8_t temp;

    // Row 1: rotate left by one position.
    temp = state[1];
    state[1] = state[5];
    state[5] = state[9];
    state[9] = state[13];
    state[13] = temp;

    // Row 2: rotate left by two positions.
    temp = state[2];
    state[2] = state[10];
    state[10] = temp;
    temp = state[6];
    state[6] = state[14];
    state[14] = temp;

    // Row 3: rotate left by three positions.
    temp = state[3];
    state[3] = state[15];
    state[15] = state[11];
    state[11] = state[7];
    state[7] = temp;
}

static void mix_columns_step(uint8_t *state) {

    for (int i = 0; i < 4; i++) {
        // The base index selects the current column: 0, 4, 8, or 12.
        int base = i * 4; 

        uint8_t a0 = state[base + 0];
        uint8_t a1 = state[base + 1];
        uint8_t a2 = state[base + 2];
        uint8_t a3 = state[base + 3];

        uint8_t r0 = xtime(a0) ^ xtime(a1) ^ a1 ^ a2 ^ a3;
        uint8_t r1 = a0 ^ xtime(a1) ^ xtime(a2) ^ a2 ^ a3;
        uint8_t r2 = a0 ^ a1 ^ xtime(a2) ^ xtime(a3) ^ a3;
        uint8_t r3 = xtime(a0) ^ a0 ^ a1 ^ a2 ^ xtime(a3);

        state[base + 0] = r0;
        state[base + 1] = r1;
        state[base + 2] = r2;
        state[base + 3] = r3;
    }
}


static void add_round_key_step(uint8_t *state, const uint8_t *round_key) {

    for (int i = 0; i < 16; i++) {
        state[i] ^= round_key[i];
    }
}

static void key_expansion(const uint8_t *Key, uint8_t *round_key) {

    // The first round key is the original key.
    for (int i = 0; i < 16; i++) {
        round_key[i] = Key[i];
    }

    // Generate the remaining round keys.
    int bytes_generated = 16;
    int rcon_iteration = 1;
    uint8_t temp[4];

    while (bytes_generated < 176) {
        // Read the last four generated bytes.
        for (int i = 0; i < 4; i++) {
            temp[i] = round_key[bytes_generated - 4 + i];
        }

        // Apply the key schedule transformation every 16 bytes.
        if (bytes_generated % 16 == 0) {
            // Rotate the bytes cyclically.
            uint8_t k = temp[0];
            temp[0] = temp[1]; temp[1] = temp[2]; temp[2] = temp[3]; temp[3] = k;

            // Substitute each byte through the S-box.
            for (int i = 0; i < 4; i++) {
                temp[i] = sbox[temp[i]];
            }

            // XOR the round constant.
            temp[0] ^= rcon[rcon_iteration++];
        }

        // Generate four bytes by XOR with the corresponding previous-round bytes.
        for (int i = 0; i < 4; i++) {
            round_key[bytes_generated] = round_key[bytes_generated - 16] ^ temp[i];
            bytes_generated++;
        }
    }

}

static void AES_encrypt_block(uint8_t *state, const uint8_t *round_key) {

    // Initial round.
    add_round_key_step(state, round_key);

    // Nine main rounds.
    for (int round = 1; round <= 9; round++) {
        sub_bytes_step(state);
        shift_rows_step(state);
        mix_columns_step(state);
        add_round_key_step(state, round_key + round * 16);
    }

    // Final round without MixColumns.
    sub_bytes_step(state);
    shift_rows_step(state);
    add_round_key_step(state, round_key + 10 * 16);
}


int my_aes_encrypt(const uint8_t *input, int input_len, uint8_t *output, const uint8_t *key) {

    uint8_t round_key[176]; // Storage for the expanded round keys.
    uint8_t block[16];     // Temporary storage for one 16-byte block.
    
    // Expand the key once per invocation.
    key_expansion(key, round_key);

    int output_len = 0;
    int i = 0;

    // Process input in 16-byte blocks.
    while (i < input_len) {
        int bytes_to_copy = (input_len - i >= 16) ? 16 : (input_len - i);
        
        // Copy input bytes into the block.
        memcpy(block, input + i, bytes_to_copy);
        
        // PKCS#7 padding for a final partial block.
        if (bytes_to_copy < 16) {
            uint8_t pad_value = 16 - bytes_to_copy;
            for (int j = bytes_to_copy; j < 16; j++) {
                block[j] = pad_value;
            }
        }

        // Encrypt the block.
        AES_encrypt_block(block, round_key);
        
        // Copy the ciphertext to the output.
        memcpy(output + output_len, block, 16);
        output_len += 16;
        i += 16;
    }

    // PKCS#7 requires an additional full padding block for an exact multiple of 16 bytes.
    // The extra block contains sixteen bytes with value 0x10.
    if (input_len % 16 == 0) {
        for (int j = 0; j < 16; j++) {
            block[j] = 16;
        }
        AES_encrypt_block(block, round_key);
        memcpy(output + output_len, block, 16);
        output_len += 16;
    }

    return output_len; // Return the padded ciphertext length.
}


void sha256_transform(uint32_t state[8], const uint8_t data[64]) {

    uint32_t a, b, c, d, e, f, g, h, i, j, t1, t2, m[64];

    // Read the first 16 schedule words from the block in big-endian order.
    for (i = 0, j = 0; i < 16; ++i, j += 4)
        m[i] = ((uint32_t)data[j] << 24) | ((uint32_t)data[j + 1] << 16) |
               ((uint32_t)data[j + 2] << 8) | (uint32_t)data[j + 3];
    
    // Derive the remaining 48 schedule words with SIG0 and SIG1.
    for (; i < 64; ++i)
        m[i] = SIG1(m[i - 2]) + m[i - 7] + SIG0(m[i - 15]) + m[i - 16];

    // Initialize working variables from the current hash state.
    a = state[0]; 
    b = state[1]; 
    c = state[2]; 
    d = state[3];
    e = state[4]; 
    f = state[5]; 
    g = state[6]; 
    h = state[7];

    // Compression rounds.
    for (i = 0; i < 64; ++i) {
        t1 = h + EP1(e) + CH(e, f, g) + k[i] + m[i];
        t2 = EP0(a) + MAJ(a, b, c);
        h = g;
        g = f;
        f = e;
        e = d + t1;
        d = c;
        c = b;
        b = a;
        a = t1 + t2;
    }

    // Add the working result to the hash state.
    state[0] += a; 
    state[1] += b; 
    state[2] += c; 
    state[3] += d;
    state[4] += e; 
    state[5] += f; 
    state[6] += g; 
    state[7] += h;
}

int my_sha256_hash(const uint8_t *input, int input_len, uint8_t *output) {
    uint32_t state[8] = {
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 
        0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
    };

    int i = 0;
    // Process complete 64-byte blocks directly from the input.
    for (i = 0; i + 64 <= input_len; i += 64) {
        sha256_transform(state, &input[i]);
    }

    // Construct the final padding in a small temporary buffer.
    uint8_t final_block[64];
    int remaining = input_len - i;
    memcpy(final_block, &input[i], remaining);
    final_block[remaining] = 0x80; // Append the mandatory one bit.
    remaining++;

    // Use an extra block if the current block cannot hold the eight-byte length.
    if (remaining > 56) {
        memset(&final_block[remaining], 0, 64 - remaining);
        sha256_transform(state, final_block);
        memset(final_block, 0, 56);
    } else {
        memset(&final_block[remaining], 0, 56 - remaining);
    }

    // Append the input length in bits, in big-endian order.
    uint64_t bit_len = (uint64_t)input_len * 8;
    for (int b = 0; b < 8; b++) {
        final_block[63 - b] = (uint8_t)(bit_len >> (b * 8));
    }
    sha256_transform(state, final_block);

    // Serialize the digest.
    for (int i = 0; i < 8; i++) {
        output[i * 4]     = (state[i] >> 24) & 0xFF;
        output[i * 4 + 1] = (state[i] >> 16) & 0xFF;
        output[i * 4 + 2] = (state[i] >> 8) & 0xFF;
        output[i * 4 + 3] = (state[i]) & 0xFF;
    }

    return 32; // Return the digest length.
}


void chacha20_quarter_round(uint32_t *a, uint32_t *b, uint32_t *c, uint32_t *d) {

    *a += *b; 
    *d ^= *a; 
    *d = ROTLEFT(*d, 16);

    *c += *d; 
    *b ^= *c; 
    *b = ROTLEFT(*b, 12);

    *a += *b; 
    *d ^= *a; 
    *d = ROTLEFT(*d, 8);

    *c += *d; 
    *b ^= *c; 
    *b = ROTLEFT(*b, 7);
}

void chacha20_mixing(uint32_t out[16], uint32_t const in[16]) {

    uint32_t temp[16];
    for (int i = 0; i < 16; ++i) {
        temp[i] = in[i];
    } 

    // Twenty rounds, alternating column and diagonal quarter-rounds.
    for (int round = 0; round < 10; round++) {
        // Apply column quarter-rounds.
        chacha20_quarter_round(&temp[0], &temp[4], &temp[8], &temp[12]);
        chacha20_quarter_round(&temp[1], &temp[5], &temp[9], &temp[13]);
        chacha20_quarter_round(&temp[2], &temp[6], &temp[10], &temp[14]);
        chacha20_quarter_round(&temp[3], &temp[7], &temp[11], &temp[15]);

        // Apply diagonal quarter-rounds.
        chacha20_quarter_round(&temp[0], &temp[5], &temp[10], &temp[15]);
        chacha20_quarter_round(&temp[1], &temp[6], &temp[11], &temp[12]);
        chacha20_quarter_round(&temp[2], &temp[7], &temp[8], &temp[13]);
        chacha20_quarter_round(&temp[3], &temp[4], &temp[9], &temp[14]);
    }

    // Add the initial state to the mixed state.
    for (int i = 0; i < 16; i++) {
        out[i] = temp[i] + in[i];
    }
}

// Read an unaligned little-endian 32-bit word safely.
static uint32_t load32_le(const uint8_t *src) {
    return (uint32_t)src[0] | ((uint32_t)src[1] << 8) | 
           ((uint32_t)src[2] << 16) | ((uint32_t)src[3] << 24);
}

int my_chacha20_encrypt(const uint8_t *input, int input_len, uint8_t *output, const uint8_t *key, const uint8_t *nonce) {

    // Initialize the ChaCha20 state (RFC 7539 layout).
    uint32_t state[16] = {
        0x61707865, 0x3320646e, 0x79622d32, 0x6b206574, // "expand 32-byte k"
        load32_le(key), load32_le(key + 4), load32_le(key + 8), load32_le(key + 12),
        load32_le(key + 16), load32_le(key + 20), load32_le(key + 24), load32_le(key + 28),
        1,                                              // Counter 
        load32_le(nonce), load32_le(nonce + 4), load32_le(nonce + 8) // Nonce 96-bit
    };

    int processed = 0;
    while (processed < input_len) {
        uint32_t keystream[16];
        chacha20_mixing(keystream, state);

        // Each keystream block contains 64 bytes.
        int bytes_to_xor = 0;
        if (input_len - processed >= 64) {
            bytes_to_xor = 64;
        } else {
            bytes_to_xor = input_len - processed;
        }

        for (int j = 0; j < bytes_to_xor; j++) {
            output[processed + j] = (uint8_t)(keystream[j/4] >> (8*(j%4))) ^ input[processed + j];
        }

        processed += bytes_to_xor;
        
        // Increment the block counter for the next 64-byte block.
        state[12]++;
    }

    return processed;
}



int my_crc32(const uint8_t *input, int input_len, uint32_t *output) {

    uint32_t crc = 0xFFFFFFFF;

    for (int i = 0; i < input_len; i++) {
        uint8_t byte = input[i];
        crc ^= byte;

        for (int j = 0; j < 8; j++) {
            if (crc & 1) {
                crc = (crc >> 1) ^ 0xEDB88320;
            } else {
                crc >>= 1;
            }
        }
    }

    *output = ~crc;
    return 0;
}



// DIGITAL SIGNAL PROCESSING ALGORITHMS

uint32_t reverse_bits(uint32_t index, int bits) {
    uint32_t reversed = 0;
    for (int i = 0; i < bits; i++) {
        if (index & (1 << i)) {
            reversed |= (1 << (bits - 1 - i));
        }
    }
    return reversed;
}


int my_fft(const uint8_t *input, int input_len, float *output) {
    
    // Require a nonzero power-of-two input length.
    if (!input || !output || input_len <= 0 || input_len > 2048 || (input_len & (input_len - 1)) != 0) {
        return -1;
    }

    float *real = fft_real_workspace;
    float *imag = fft_imag_workspace;
    int stages = 0;
    for (int remaining = input_len; remaining > 1; remaining >>= 1) ++stages;

    // Reorder the input using bit reversal.
    for (int i = 0; i < input_len; i++) {
        uint32_t rev_i = reverse_bits(i, stages);
        real[rev_i] = (float)input[i];
        imag[rev_i] = 0.0f;
    }

    // Apply the iterative FFT.
    for (int s = 1; s <= stages; s++) {
        int m = 1 << s; // m = 2^s
        double wm_real = cos(2 * PI / m);
        double wm_imag = -sin(2 * PI / m);

        for (int k = 0; k < input_len; k += m) {
            double w_real = 1.0;
            double w_imag = 0.0;

            for (int j = 0; j < m / 2; j++) {
                int t_index = k + j + m / 2;
                double t_real = w_real * real[t_index] - w_imag * imag[t_index];
                double t_imag = w_real * imag[t_index] + w_imag * real[t_index];

                int u_index = k + j;
                double u_real = real[u_index];
                double u_imag = imag[u_index];

                real[u_index] = u_real + t_real;
                imag[u_index] = u_imag + t_imag;
                real[t_index] = u_real - t_real;
                imag[t_index] = u_imag - t_imag;

                // Update the twiddle factor for the next iteration.
                double temp_w_real = w_real * wm_real - w_imag * wm_imag;
                w_imag = w_real * wm_imag + w_imag * wm_real;
                w_real = temp_w_real;
            }
        }
    }

    // Write normalized magnitudes to the float output.
    for (int i = 0; i < input_len; i++) {
        output[i] = (float)(sqrt((double)real[i] * real[i] + (double)imag[i] * imag[i]) / input_len);
    }

    return 0;
}


int my_fir_filter(const uint8_t *input, int input_len, uint8_t *output, const uint8_t *coefficients, int num_coefficients) {
    
    if (input == NULL || output == NULL || coefficients == NULL) {
        return -1;
    }

    // Process every input sample.
    for (int n = 0; n < input_len; n++) {
        uint32_t accumulator = 0;

        // Apply the filter to the current sample.
        for (int k = 0; k < num_coefficients; k++) {
            // Treat unavailable past samples as zero.
            if (n - k >= 0) {
                accumulator += (uint32_t)input[n - k] * (uint32_t)coefficients[k];
            }
        }

        // Normalize by the coefficient sum using integer division.
        uint32_t sum_coeffs = 0;
        for(int i = 0; i < num_coefficients; i++) {
            sum_coeffs += coefficients[i];
        }
        if (sum_coeffs > 0) {
            output[n] = (uint8_t)(accumulator / sum_coeffs);
        } else {
            output[n] = (uint8_t)accumulator; 
        }
    }

    return 0; 
}


int my_iir_filter(const uint8_t *input, int input_len, uint8_t *output, const uint8_t *b_coefficients, int num_b_coefficients, const uint8_t *a_coefficients, int num_a_coefficients) {

    if (input == NULL || output == NULL || b_coefficients == NULL || a_coefficients == NULL) {
        return -1;
    }

    // Calculate the sum of the feedforward coefficients.
    double sum_b = 0.0;
    for(int m = 0; m < num_b_coefficients; m++) {
        sum_b += b_coefficients[m];
    }

    for (int i = 0; i < input_len; i++) {
        double acc_b = 0.0;
        double acc_a = 0.0;

        // Feedforward contribution (b_coefficients).
        for (int j = 0; j < num_b_coefficients; j++) {
            if (i - j >= 0) {
                acc_b += b_coefficients[j] * input[i - j];
            }
        }

        // Feedback contribution (a_coefficients).
        for (int k = 1; k < num_a_coefficients; k++) {
            if (i - k >= 0) {
                acc_a += (double)a_coefficients[k] * output[i - k];
            }
        }

        double final_result;
        if (sum_b > 0) {
            // Divide by the feedforward coefficient sum; feedback can still amplify the signal.
            final_result = (acc_b + acc_a) / sum_b;
        } else {
            final_result = (acc_b + acc_a);
        }

        // Clamp to the unsigned-byte range before storing the feedback sample.
        if (final_result > 255.0) final_result = 255.0;
        if (final_result < 0.0) final_result = 0.0;

        output[i] = (uint8_t)final_result;
    }

    return 0;
}


int my_dct(const uint8_t *input, int input_len, float *output) {
    if (input == NULL || output == NULL || input_len <= 0) {
        return -1;
    }

    float factor = PI / (2.0f * (float)input_len);
    float sqrt_1_n = sqrtf(1.0f / (float)input_len);
    float sqrt_2_n = sqrtf(2.0f / (float)input_len);

    for (int k = 0; k < input_len; k++) {
        float sum = 0.0f;
        for (int n = 0; n < input_len; n++) {
            /* DCT-II angle, reduced by exact integer periods before cosf.
             * Keeping the angle in [0,2*pi) avoids large-argument float loss.
             */
            uint32_t phase = ((uint32_t)k * (2u*(uint32_t)n + 1u)) % (4u*(uint32_t)input_len);
            sum += (float)input[n] * cosf(factor * (float)phase);
        }

        float ck = 0;
        if (k == 0) {
            ck = sqrt_1_n;
        } else {
            ck = sqrt_2_n;
        }

        float dct_value = ck * sum;

        output[k] = dct_value;
    }

    return 0;
}
