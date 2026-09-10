#ifndef BENCH_ORIGINAL_PRIVATE_H
#define BENCH_ORIGINAL_PRIVATE_H
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

/* DEFINE-uri pentru functia my_lz77_encode */
#define MAX_WINDOW_SIZE_LZ77 255
#define MAX_LOOKAHEAD_SIZE_LZ77 255

/* Structuri pentru functia my_huffman_encode - treeless + canonical Huffman */

// Structura tip element din minheap
typedef struct {
    uint32_t freq;
    uint16_t branch_id; // ID-ul ramurii din care face parte - A-65, B-66, etc. sau ID-ul nodului intern daca nu e frunza
} minheap_element;

// Structura pentru coduri
typedef struct {
    uint8_t len;        // Lungimea finala a codului
    uint32_t code;      // Codul canonic efectiv generat (max 32 biti)
} canonical_code;

typedef struct {
    minheap_element heap[256];
    uint16_t heap_size;
    
    // Tabele pentru logica "Treeless"
    uint8_t lengths[256];     // Lungimea codului pentru fiecare caracter (0-255)
    uint16_t branch_ids[256]; // Ce ramura apartine fiecare caracter
    uint8_t is_active[256];   // 1 daca acel caracter exista in datele noastre
    
    canonical_code codes[256]; // Tabelul final de coduri
} TreelessEnv;

// Functie ajutatoare pentru my_huffman_encode - extrage nodul cu cea mai mica frecventa de aparitie
static minheap_element extract_min_node(TreelessEnv *env);

// Functie ajutatoare pentru my_huffman_encode - insereaza un nod in minheap
static void insert_node_in_minheap(TreelessEnv *env, minheap_element node);

// Functie ajutatoare pentru my_huffman_encode - sorteaza codurile generate in functie de lungime (alfabetic pt
// coduri de aceeasi lungime)
static void sort_codes_by_length(TreelessEnv *env, uint8_t *elements, int num_elements);


/* Lucuri de folosinta pentru AES-128 */
// S-BOX-ul pentru AES-128 (substitutie)
static const uint8_t sbox[256] = {
    0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
    0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
    0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
    0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
    0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
    0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
    0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
    0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
    0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
    0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
    0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
    0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
    0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
    0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
    0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
    0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16
};

// Round Constants (Rcon): Folosite in procesul de Key Expansion
static const uint8_t rcon[11] = {
    0x8d, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36
};

// Functie pentru operatii in campul Galois necesara pentru MixColumns
static uint8_t xtime(uint8_t x);

// Inlocuieste fiecare octet folosind S-BOX-ul definit mai sus
static void sub_bytes_step(uint8_t *state);

// Roteste randurile matricei de stare
static void shift_rows_step(uint8_t *state);

// Amesteca coloanele matricei de stare folosind operatii in campul Galois
static void mix_columns_step(uint8_t *state);

// Adauga cheia la matrice folosind operatia XOR
static void add_round_key_step(uint8_t *state, const uint8_t *round_key);

// Genereaza cheile pentru fiecare runda folosind cheia initiala
static void key_expansion(const uint8_t *Key, uint8_t *round_key);

// Cripteaza un bloc de 16 octeti folosind cheia de runda curenta
static void AES_encrypt_block(uint8_t *state, const uint8_t *round_key);


// Folositoare pentru SHA-256
// Macro-uri pentru operații logice specifice SHA-256
#define ROTRIGHT(word, bits) (((word) >> (bits)) | ((word) << (32 - (bits))))
#define CH(x, y, z) (((x) & (y)) ^ (~(x) & (z)))
#define MAJ(x, y, z) (((x) & (y)) ^ ((x) & (z)) ^ ((y) & (z)))
#define EP0(x) (ROTRIGHT(x, 2) ^ ROTRIGHT(x, 13) ^ ROTRIGHT(x, 22))
#define EP1(x) (ROTRIGHT(x, 6) ^ ROTRIGHT(x, 11) ^ ROTRIGHT(x, 25))
#define SIG0(x) (ROTRIGHT(x, 7) ^ ROTRIGHT(x, 18) ^ ((x) >> 3))
#define SIG1(x) (ROTRIGHT(x, 17) ^ ROTRIGHT(x, 19) ^ ((x) >> 10))

// Constantele K (primele 32 de biți din părțile fracționare ale rădăcinilor cubice)
static const uint32_t k[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
};

void sha256_transform(uint32_t state[8], const uint8_t data[64]);


// Folositoare pentru ChaCha20
#define ROTLEFT(a, b) (((a) << (b)) | ((a) >> (32 - (b))));

// Functie pentru mixarea celor 4 cuvinte dintr-un quarter round
void chacha20_quarter_round(uint32_t *a, uint32_t *b, uint32_t *c, uint32_t *d);

// Functie pentru amestecarea celor 16 cuvinte din starea ChaCha20 folosind 20 de runde
void chacha20_mixing(uint32_t out[16], uint32_t const in[16]);


// Folositoare pentru FFT

# define PI 3.14159265358979323846

// Functie pentru inversarea bitilor
uint32_t reverse_bits(uint32_t index, int bits);



#ifdef __cplusplus
extern "C" {
#endif

// ALGORITMI DE COMPRESIE 

/* 1. RLE (Run-Length Encoding) - metoda de compresie care inlocuieste secvente de date repetitive cu o singura valoare si cu
numarul de repetari ale acesteia.*/
int my_rle_encode(const uint8_t *input, int input_len, uint8_t *output);

/* 2. Delta encoding - metoda de compresie care inregistreaza diferentele dintre valori consecutive */
int my_delta_encode(const uint8_t *input, int input_len, uint8_t *output);

/* 3. LZ77 - metoda de compresie care inlocuieste secvente de date repetitive cu referinte catre datele anterioare */
int my_lz77_encode(const uint8_t *input, int input_len, uint8_t *output);

/* 4. Huffman coding - metoda de compresie care atribuie coduri binare de lungime variabilă în funcție de frecvența apariției fiecărui simbol */
int my_huffman_encode(const uint8_t *input, int input_len, uint8_t *output);


// ALGORITMI DE CRIPTARE + INTEGRITATE A DATELOR

/* 5. AES - metoda de criptare simetrică care utilizează un cheie de 128, 192 sau 256 biți */
int my_aes_encrypt(const uint8_t *input, int input_len, uint8_t *output, const uint8_t *key);

/* 6. SHA-256 - metoda de hash care produce un rezultat de 256 biți */
int my_sha256_hash(const uint8_t *input, int input_len, uint8_t *output);

/* 7. ChaCha20 - metoda de criptare simetrică care utilizează un cheie de 256 biți */
int my_chacha20_encrypt(const uint8_t *input, int input_len, uint8_t *output, const uint8_t *key, const uint8_t *nonce);

/* 8. CRC - metoda de verificare a integrității datelor */
int my_crc32(const uint8_t *input, int input_len, uint32_t *output);


// ALGORITMI DE PROCESARE A SEMNALELOR DIGITALE

/* 9. FFT (Fast Fourier Transform) - metoda de transformare a unui semnal din domeniul timp în domeniul frecvență */
int my_fft(const uint8_t *input, int input_len, float *output);

/* 10. FIR (Finite Impulse Response) - metoda de filtrare a semnalelor digitale */
int my_fir_filter(const uint8_t *input, int input_len, uint8_t *output, const uint8_t *coefficients, int num_coefficients);

/* 11. IIR (Infinite Impulse Response) - metoda de filtrare a semnalelor digitale */
int my_iir_filter(const uint8_t *input, int input_len, uint8_t *output, const uint8_t *b_coefficients, int num_b_coefficients, const uint8_t *a_coefficients, int num_a_coefficients);

/* 12. DCT (Discrete Cosine Transform) - metoda de transformare a unui semnal în domeniul frecvență */
int my_dct(const uint8_t *input, int input_len, float *output);


#ifdef __cplusplus
}
#endif
#endif
