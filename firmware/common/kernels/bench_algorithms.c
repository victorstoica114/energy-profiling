/* Derived from the recovered Noela Pirleci benchmark library.
 * Repairs are recorded in this project's tests/kernel_tests/README.md.
 * This file intentionally preserves the original scalar algorithms.
 */
#include "bench_original_private.h"

static float fft_real_workspace[2048];
static float fft_imag_workspace[2048];

// ALGORITMI DE COMPRESIE


int my_rle_encode(const uint8_t *input, int input_len, uint8_t *output) {
    if (input_len == 0) {
        return 0;
    }
    int out_idx = 0;
    for (int i = 0; i < input_len; i++) {
        uint8_t count = 1;
        
        /* Numaram aparitiile consecutive ale aceleiasi valori.
        Daca am ajuns la finalul vectorului sau gasim o valoare diferita
        la urmatorul pas sau atingem limita maxima pentru un intreg, atunci
        salvam rezultatul curent. Altfel, continuam numaratul.*/
        while (i + 1 < input_len && input[i] == input[i + 1] && count < 255) {
            count++;
            i++;
        }
        
        /* Salvam rezultatul de la momentul curent */
        output[out_idx++] = count;
        output[out_idx++] = input[i];
    }
    
    /* Returnam dimensiunea vectorului in urma operatiei de compresie. */
    return out_idx;
}


int my_delta_encode(const uint8_t *input, int input_len, uint8_t *output) {

    if (input_len == 0) {
        return 0;
    }

    /* Vom adauga prima valoarea din input in output */
    output[0] = input[0];

    /* Vom adauga in output diferentele dintre valorile consecutive pe care le gasim
    in input */
    for (int i = 1; i < input_len; i++ ) {
        output[i] = input[i] - input[i - 1];
    }

    /* Returnam dimensiunea vectorului in urma operatiei de compresie. !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!*/
    return input_len; 
}


int my_lz77_encode(const uint8_t *input, int input_len, uint8_t *output) {

    int out_idx = 0;
    int cursor = 0;

    while (cursor < input_len) {

        int max_match_len = 0;
        int max_match_dist = 0;
        int history_limit_start;

        /* Vom stabili limita istoricului (pana unde putem cauta in urma pentru
        o secventa care se repeta) */
        if (cursor < MAX_WINDOW_SIZE_LZ77) {
            history_limit_start = 0;
        } else {
            history_limit_start = cursor - MAX_WINDOW_SIZE_LZ77;
        }

        /* Cautam in istoric cea mai lunga potrivire */
        for (int i = history_limit_start; i < cursor; i++) {
            int current_match_len = 0;
            /* Modific lungimea potrivirii curente cata vreme:
                1. Nu depasim limita buffer-ului 
                2. Nu depasim lungimea textului de input
                3. Caracterul curent se potriveste */
            while ((current_match_len < MAX_LOOKAHEAD_SIZE_LZ77) &&
                   (cursor + current_match_len < input_len) &&
                   (input[i + current_match_len] == input[cursor + current_match_len])) {
                current_match_len++;
            }

            /* Daca am gasit o potrivire de lungime mai mare decat ceea ce 
            aveam deja, o vom inlocui si vom recalcula distanta pana la acea
            potrivire noua (cati pasi inapoi facem pentru a ajunge la ea) */
            if (current_match_len > max_match_len) {
                max_match_len = current_match_len;
                max_match_dist = cursor - i;
            }
        }

        /* Luam urmatorul caracter din look-ahead buffer */
        uint8_t next_char = 0;
        if (cursor + max_match_len < input_len) {
            next_char = input[cursor + max_match_len];
        }

        /* Salvam tripletul (distanta, lungime, caracter) / rezultatul */
        output[out_idx++] = (uint8_t)max_match_dist;
        output[out_idx++] = (uint8_t)max_match_len;
        if (cursor + max_match_len < input_len) {
            output[out_idx++] = next_char;
        }

        /* Mutam cursorul la urmatorul caracter */
        cursor += max_match_len;
        if (cursor < input_len) ++cursor;
    }

    /* Returnam dimensiunea vectorului in urma operatiei de compresie. */
    return out_idx;
}

static minheap_element extract_min_node(TreelessEnv *env) {

    uint32_t min_freq = 0xFFFFFFFF;
    int min_idx = -1;

    /* Cautam nodul cu frecventa minima */
    for (int i = 0; i < env->heap_size; i++) {
        if (env->heap[i].freq < min_freq ||
            (min_idx >= 0 && env->heap[i].freq == min_freq &&
             env->heap[i].branch_id < env->heap[min_idx].branch_id)) {
            min_freq = env->heap[i].freq;
            min_idx = i;
        }
    }

    /* Extragem nodul cu frecventa minima */
    minheap_element min_node = env->heap[min_idx];

    /* Mutam ultimul element in locul celui pe care l-am extras si reducem dimensiunea heap-ului */
    env->heap[min_idx] = env->heap[env->heap_size - 1];
    env->heap_size--;

    /* Returnam nodul cautat - cel cu cea mai mica frecventa */
    return min_node;
}

static void insert_node_in_minheap(TreelessEnv *env, minheap_element node) {

    /* Adaugam un nou nod in minheap */
    env->heap[env->heap_size] = node;
    env->heap_size++;
}

static void sort_codes_by_length(TreelessEnv *env, uint8_t *elements, int num_elements) {

    /* Sortam codurile generate in functie de lungime (alfabetic pt coduri de aceeasi lungime) */
    for (int i = 0; i < num_elements - 1; i++) {
        for (int j = i + 1; j < num_elements; j++) {
            
            // Luam elementele curente pentru comparatie
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

    // In loc de calloc, folosim static pentru a aloca in segmentul de date, nu pe heap
    // Atentie: asta face functia non-reentranta (nu o poti rula pe 2 thread-uri simultan)
    static TreelessEnv env_static; 
    TreelessEnv *env = &env_static;
    memset(env, 0, sizeof(TreelessEnv)); // Curatam memoria

    /* Calculam frecventa fiecarui caracter din input */
    uint32_t freqs[256] = {0};
    for (int i = 0; i < input_len; i++) {
        freqs[input[i]]++;
    }

    /* Adaugam in minheap nodurile corespunzatoare fiecarui caracter, alaturi de frecventele lor */
    for (int i = 0; i < 256; i++) {
        if (freqs[i] > 0) {
            minheap_element new_node = {freqs[i], (uint16_t)i}; // branch_id este caracterul in sine pentru nodurile frunza
            insert_node_in_minheap(env, new_node);
            env->is_active[i] = 1;                              // Marcam caracterul ca fiind activ
            env->branch_ids[i] = (uint16_t)i;                   // Initial, fiecare caracter apartine unei "ramuri" care este el insusi
        }
    }

    uint16_t next_branch_id = 256;   // ID-urile pt nodurile interne vor incepe de la 256

    /* Incepem constructia arborelui Huffman */
    while (env->heap_size > 1) {
        // Extragem cele doua noduri cu frecventa minima
        minheap_element min1 = extract_min_node(env);
        minheap_element min2 = extract_min_node(env);

        // Cream un nou nod intern care va avea ca frecventa suma celor doua noduri extrase
        minheap_element new_node;
        new_node.freq = min1.freq + min2.freq;
        new_node.branch_id = next_branch_id++; // ID unic pentru nodul intern

        // Adaugam noul nod in minheap
        insert_node_in_minheap(env, new_node);

        // Actualizam branch_ids pentru caracterele din ramurile celor doua noduri extrase
        // Pentru fiecare caracter activ, verificam daca acesta apartine ramurii min1 sau min2 pentru a stii daca 
        // trebuie sa ii schimbam branch_id-ul la noul nod intern
        for (int i = 0; i < 256; i++) {
            if (env->is_active[i]) {
                if (env->branch_ids[i] == min1.branch_id || env->branch_ids[i] == min2.branch_id) {
                    env->branch_ids[i] = new_node.branch_id;
                    env->lengths[i]++;
                }
            }
        }
    }

    /* Vom sorta codurile pentru elementele active */
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

        // Daca lungimea creste, shiftam la stanga codul existent
        while (current_length < env->lengths[elem]) {
            current_code <<= 1;
            current_length++;
        }
        
        env->codes[elem].code = current_code;
        env->codes[elem].len = current_length;
        
        current_code++; // Incrementam pentru urmatorul simbol de aceeasi lungime
    }


    /* Construim codurile (bitii) pentru a returna */
    uint32_t payload_bits = 0;
    for (int i = 0; i < input_len; ++i) payload_bits += env->codes[input[i]].len;
    for (int b = 0; b < 4; ++b) output[4+b] = (uint8_t)(payload_bits >> (8*b));
    output += 264;
    int out_byte_idx = 0;
    int out_bit_idx = 0;
    output[0] = 0; // Initializam primul byte al output-ului

    for (int i = 0; i < input_len; i++) {

        uint8_t elem = input[i];
        canonical_code code_info = env->codes[elem];

        for (int bit_pos = code_info.len - 1; bit_pos >= 0; bit_pos--) {
            uint8_t bit = (code_info.code >> bit_pos) & 1;

            // Setam bitul curent in output
            output[out_byte_idx] |= (bit << (7 - out_bit_idx));
            out_bit_idx++;

            // Daca am umplut un byte, trecem la urmatorul
            if (out_bit_idx == 8) {
                out_bit_idx = 0;
                out_byte_idx++;
                if ((uint32_t)out_byte_idx * 8u < payload_bits) output[out_byte_idx] = 0;
            }
        }
    }

    /* Returnam dimensiunea vectorului in urma operatiei de compresie. */
    int total_bytes = out_byte_idx + (out_bit_idx > 0 ? 1 : 0);
    return 264 + total_bytes;
}



// ALGORITMI DE CRIPTARE + INTEGRITATE A DATELOR


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

    // Randul 1: rotire la stanga cu 1 pozitie
    temp = state[1];
    state[1] = state[5];
    state[5] = state[9];
    state[9] = state[13];
    state[13] = temp;

    // Randul 2: rotire la stanga cu 2 pozitii
    temp = state[2];
    state[2] = state[10];
    state[10] = temp;
    temp = state[6];
    state[6] = state[14];
    state[14] = temp;

    // Randul 3: rotire la stanga cu 3 pozitii (sau la dreapta cu 1 pozitie)
    temp = state[3];
    state[3] = state[15];
    state[15] = state[11];
    state[11] = state[7];
    state[7] = temp;
}

static void mix_columns_step(uint8_t *state) {

    for (int i = 0; i < 4; i++) {
        // 'base' este indexul de start pentru coloana curenta (0, 4, 8, 12)
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

    // Prima sub-cheie este chiar cheia initiala
    for (int i = 0; i < 16; i++) {
        round_key[i] = Key[i];
    }

    // Generam celelalte sub-chei pentru fiecare runda
    int bytes_generated = 16;
    int rcon_iteration = 1;
    uint8_t temp[4];

    while (bytes_generated < 176) {
        // Citim ultimii 4 octeti generati
        for (int i = 0; i < 4; i++) {
            temp[i] = round_key[bytes_generated - 4 + i];
        }

        // La fiecare 16 octeti aplicam transformarea speciala a cheii
        if (bytes_generated % 16 == 0) {
            // rotim circular octetii
            uint8_t k = temp[0];
            temp[0] = temp[1]; temp[1] = temp[2]; temp[2] = temp[3]; temp[3] = k;

            // substituim fiecare octet folosind S-BOX-ul
            for (int i = 0; i < 4; i++) {
                temp[i] = sbox[temp[i]];
            }

            // XOR cu rcon
            temp[0] ^= rcon[rcon_iteration++];
        }

        // Generam urmatorii 4 octeti aplicand XOR cu corespondentul de la iteratia anterioara
        for (int i = 0; i < 4; i++) {
            round_key[bytes_generated] = round_key[bytes_generated - 16] ^ temp[i];
            bytes_generated++;
        }
    }

}

static void AES_encrypt_block(uint8_t *state, const uint8_t *round_key) {

    // Runda initiala
    add_round_key_step(state, round_key);

    // 9 runde principale
    for (int round = 1; round <= 9; round++) {
        sub_bytes_step(state);
        shift_rows_step(state);
        mix_columns_step(state);
        add_round_key_step(state, round_key + round * 16);
    }

    // Runda finala (fara mix_columns)
    sub_bytes_step(state);
    shift_rows_step(state);
    add_round_key_step(state, round_key + 10 * 16);
}


int my_aes_encrypt(const uint8_t *input, int input_len, uint8_t *output, const uint8_t *key) {

    uint8_t round_key[176]; // Buffer pentru toate sub-cheile
    uint8_t block[16];     // Buffer temporar pentru un singur bloc de 16 octeti
    
    // 1. Expandam cheia o singura data la inceput
    key_expansion(key, round_key);

    int output_len = 0;
    int i = 0;

    // 2. Parcurgem textul din 16 in 16 octeti
    while (i < input_len) {
        int bytes_to_copy = (input_len - i >= 16) ? 16 : (input_len - i);
        
        // Copiem datele in bloc
        memcpy(block, input + i, bytes_to_copy);
        
        // 3. PKCS#7 Padding: Daca ajungem la final si blocul nu e plin
        if (bytes_to_copy < 16) {
            uint8_t pad_value = 16 - bytes_to_copy;
            for (int j = bytes_to_copy; j < 16; j++) {
                block[j] = pad_value;
            }
        }

        // Criptam blocul
        AES_encrypt_block(block, round_key);
        
        // Mutam rezultatul in buffer-ul de output
        memcpy(output + output_len, block, 16);
        output_len += 16;
        i += 16;
    }

    // 4. PKCS#7 Padding: Daca lungimea initiala a fost un multiplu exact de 16,
    // standardul cere sa mai adaugam un bloc intreg de padding (16 octeti de 0x10)
    if (input_len % 16 == 0) {
        for (int j = 0; j < 16; j++) {
            block[j] = 16;
        }
        AES_encrypt_block(block, round_key);
        memcpy(output + output_len, block, 16);
        output_len += 16;
    }

    return output_len; // Returnam lungimea noului sir criptat
}


void sha256_transform(uint32_t state[8], const uint8_t data[64]) {

    uint32_t a, b, c, d, e, f, g, h, i, j, t1, t2, m[64];

    // Primii 16 termeni sunt blocul de date original (convertit la big-endian)
    for (i = 0, j = 0; i < 16; ++i, j += 4)
        m[i] = ((uint32_t)data[j] << 24) | ((uint32_t)data[j + 1] << 16) |
               ((uint32_t)data[j + 2] << 8) | (uint32_t)data[j + 3];
    
    // Urmatorii 48 de termeni sunt derivati folosind functiile SIG0 și SIG1
    for (; i < 64; ++i)
        m[i] = SIG1(m[i - 2]) + m[i - 7] + SIG0(m[i - 15]) + m[i - 16];

    // Initializarea variabilelor de lucru cu starea curenta
    a = state[0]; 
    b = state[1]; 
    c = state[2]; 
    d = state[3];
    e = state[4]; 
    f = state[5]; 
    g = state[6]; 
    h = state[7];

    // Pasul de compresie
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

    // Adaugam rezultatul la starea curenta
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
    // Procesăm blocurile întregi de 64 octeți direct din input
    for (i = 0; i + 64 <= input_len; i += 64) {
        sha256_transform(state, &input[i]);
    }

    // Gestionăm padding-ul manual într-un buffer temporar mic
    uint8_t final_block[64];
    int remaining = input_len - i;
    memcpy(final_block, &input[i], remaining);
    final_block[remaining] = 0x80; // Adăugăm bitul de 1
    remaining++;

    // Dacă nu mai avem loc de lungime (8 bytes) în blocul curent
    if (remaining > 56) {
        memset(&final_block[remaining], 0, 64 - remaining);
        sha256_transform(state, final_block);
        memset(final_block, 0, 56);
    } else {
        memset(&final_block[remaining], 0, 56 - remaining);
    }

    // Adăugăm lungimea la final (în biți, big-endian)
    uint64_t bit_len = (uint64_t)input_len * 8;
    for (int b = 0; b < 8; b++) {
        final_block[63 - b] = (uint8_t)(bit_len >> (b * 8));
    }
    sha256_transform(state, final_block);

    // Scriem rezultatul
    for (int i = 0; i < 8; i++) {
        output[i * 4]     = (state[i] >> 24) & 0xFF;
        output[i * 4 + 1] = (state[i] >> 16) & 0xFF;
        output[i * 4 + 2] = (state[i] >> 8) & 0xFF;
        output[i * 4 + 3] = (state[i]) & 0xFF;
    }

    return 32; // Returnăm lungimea hash-ului
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

    // 20 de runde de quarter round
    for (int round = 0; round < 10; round++) {
        // aplicam quarter round pe coloane
        chacha20_quarter_round(&temp[0], &temp[4], &temp[8], &temp[12]);
        chacha20_quarter_round(&temp[1], &temp[5], &temp[9], &temp[13]);
        chacha20_quarter_round(&temp[2], &temp[6], &temp[10], &temp[14]);
        chacha20_quarter_round(&temp[3], &temp[7], &temp[11], &temp[15]);

        // aplicam quarter round pe diagonale
        chacha20_quarter_round(&temp[0], &temp[5], &temp[10], &temp[15]);
        chacha20_quarter_round(&temp[1], &temp[6], &temp[11], &temp[12]);
        chacha20_quarter_round(&temp[2], &temp[7], &temp[8], &temp[13]);
        chacha20_quarter_round(&temp[3], &temp[4], &temp[9], &temp[14]);
    }

    // punem rezultatul final in output adunand la starea initiala
    for (int i = 0; i < 16; i++) {
        out[i] = temp[i] + in[i];
    }
}

// Funcție ajutătoare pentru citirea sigură a unui uint32_t din orice adresă
static uint32_t load32_le(const uint8_t *src) {
    return (uint32_t)src[0] | ((uint32_t)src[1] << 8) | 
           ((uint32_t)src[2] << 16) | ((uint32_t)src[3] << 24);
}

int my_chacha20_encrypt(const uint8_t *input, int input_len, uint8_t *output, const uint8_t *key, const uint8_t *nonce) {

    // Initializare starea ChaCha20 (RFC 7539)
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

        // Un bloc are 64 octeti
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
        
        // Incrementam counter-ul pentru urmatorul bloc de 64 octeti
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



// ALGORITMI DE PROCESARE A SEMNALELOR DIGITALE

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
    
    // 1. Verificam daca lungimea input-ului este o putere a lui 2
    if (!input || !output || input_len <= 0 || input_len > 2048 || (input_len & (input_len - 1)) != 0) {
        return -1;
    }

    float *real = fft_real_workspace;
    float *imag = fft_imag_workspace;
    int stages = 0;
    for (int remaining = input_len; remaining > 1; remaining >>= 1) ++stages;

    // 2. Reordonam input-ul folosind bit-reversal  
    for (int i = 0; i < input_len; i++) {
        uint32_t rev_i = reverse_bits(i, stages);
        real[rev_i] = (float)input[i];
        imag[rev_i] = 0.0f;
    }

    // 3. Aplicam algoritmul FFT iterativ
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

                // Actualizam w pentru urmatoarea iteratie
                double temp_w_real = w_real * wm_real - w_imag * wm_imag;
                w_imag = w_real * wm_imag + w_imag * wm_real;
                w_real = temp_w_real;
            }
        }
    }

    // 4. Copiem rezultatul in output
    for (int i = 0; i < input_len; i++) {
        output[i] = (float)(sqrt((double)real[i] * real[i] + (double)imag[i] * imag[i]) / input_len);
    }

    return 0;
}


int my_fir_filter(const uint8_t *input, int input_len, uint8_t *output, const uint8_t *coefficients, int num_coefficients) {
    
    if (input == NULL || output == NULL || coefficients == NULL) {
        return -1;
    }

    // 1. Vom parcurge fiecare esantion din input
    for (int n = 0; n < input_len; n++) {
        uint32_t accumulator = 0;

        // Vom aplica filtrul pe esantionul curent
        for (int k = 0; k < num_coefficients; k++) {
            // Verificare pentru a nu accesa indecsi care nu exista pentru primele esantioane
            if (n - k >= 0) {
                accumulator += (uint32_t)input[n - k] * (uint32_t)coefficients[k];
            }
        }

        // Normalizare simpla pentru a ramane în gama 0-255
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

    // Calculam suma coeficientilor b
    double sum_b = 0.0;
    for(int m = 0; m < num_b_coefficients; m++) {
        sum_b += b_coefficients[m];
    }

    for (int i = 0; i < input_len; i++) {
        double acc_b = 0.0;
        double acc_a = 0.0;

        // Partea FIR (b_coefficients)
        for (int j = 0; j < num_b_coefficients; j++) {
            if (i - j >= 0) {
                acc_b += b_coefficients[j] * input[i - j];
            }
        }

        // Partea IIR (a_coefficients)
        for (int k = 1; k < num_a_coefficients; k++) {
            if (i - k >= 0) {
                acc_a += (double)a_coefficients[k] * output[i - k];
            }
        }

        double final_result;
        if (sum_b > 0) {
            // Normalizam suma coeficientilor b pentru a preveni amplificarea semnalului
            final_result = (acc_b + acc_a) / sum_b;
        } else {
            final_result = (acc_b + acc_a);
        }

        // Protectie pentru overflow si underflow
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
