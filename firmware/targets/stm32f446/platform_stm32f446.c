#include "bench_platform.h"
#include "bench_config.h"
#include "stm32f4xx.h"

#if !defined(STM32F446xx)
#error "This platform requires the actual STM32F446 CMSIS device and startup"
#endif
#if !defined(__ARM_FP) || ((__ARM_FP & 4) == 0) || defined(__SOFTFP__)
#error "STM32F446 requires hard-float single-precision FPU code"
#endif
#if HSI_VALUE != 16000000U
#error "This independent-power profile uses the factory-trimmed 16 MHz HSI"
#endif
_Static_assert(BENCH_EXPECTED_CPU_HZ == 100000000u, "CPU profile mismatch");
_Static_assert(BENCH_EXPECTED_OSCILLATOR_HZ == 16000000u, "HSI profile mismatch");
_Static_assert(BENCH_SIGNAL_GPIO_PORT == 2, "This target uses GPIOC");
_Static_assert(BENCH_PIN_RUN == 0 && BENCH_PIN_ID0 == 1 && BENCH_PIN_ID1 == 2 &&
    BENCH_PIN_ID2 == 3 && BENCH_PIN_ID3 == 4 && BENCH_PIN_IDLE == 5 &&
    BENCH_PIN_ERROR == 6 && BENCH_PIN_DONE == 7, "PC0..PC7 signal map required");

/* HSI/16 *200 /2: SYSCLK100 MHz. Q/5 and R/2 are valid but unused. */
#define PLL_CONFIG (16u | (200u << 6) | (5u << 24) | (2u << 28))
#define BUS_CONFIG (RCC_CFGR_PPRE1_DIV4 | RCC_CFGR_PPRE2_DIV2)
#define FPU_ACCESS (0xfu << 20)
static bool configured;

void bench_platform_signals(unsigned id, bool run, bool idle, bool error, bool done)
{
    GPIOC->BSRR = 1u << 16;
    uint32_t bits = ((id & 15u) << 1) | ((uint32_t)idle << 5) |
        ((uint32_t)error << 6) | ((uint32_t)done << 7);
    GPIOC->BSRR = ((~bits & 0xffu) << 16) | bits;
    __DMB();
    if (run) GPIOC->BSRR = 1u;
}

static bool wait_ready(volatile uint32_t *reg, uint32_t mask, uint32_t expected)
{
    for (uint32_t attempts = 0; attempts < 4000000u; ++attempts)
        if ((*reg & mask) == expected) return true;
    return false;
}

#if BENCH_DIAGNOSTICS
static bool uart_ready;
static void diagnostic_uart_init(void)
{
    RCC->APB1ENR |= RCC_APB1ENR_USART2EN;
    (void)RCC->APB1ENR;
    /* PA2 AF7 is USART2_TX to onboard ST-Link VCP. RX is not required. */
    GPIOA->MODER = (GPIOA->MODER & ~(3u << 4)) | (2u << 4);
    GPIOA->OTYPER &= ~(1u << 2);
    GPIOA->OSPEEDR = (GPIOA->OSPEEDR & ~(3u << 4)) | (1u << 4);
    GPIOA->PUPDR &= ~(3u << 4);
    GPIOA->AFR[0] = (GPIOA->AFR[0] & ~(15u << 8)) | (7u << 8);
    USART2->CR1 = 0; USART2->CR2 = 0; USART2->CR3 = 0;
    uart_ready = true;
}
static void uart_character(char value)
{
    while ((USART2->SR & USART_SR_TXE) == 0) __NOP();
    USART2->DR = (uint8_t)value;
}
static void uart_text(const char *text)
{
    while (*text) uart_character(*text++);
}
static void uart_unsigned(uint32_t value)
{
    char buffer[10]; unsigned used = 0;
    do { buffer[used++] = (char)('0' + value % 10u); value /= 10u; } while (value);
    while (used) uart_character(buffer[--used]);
}
static void uart_hex(uint32_t value)
{
    for (int shift = 28; shift >= 0; shift -= 4)
        uart_character("0123456789abcdef"[(value >> shift) & 15u]);
}
void bench_platform_report(const char *event, unsigned id, unsigned calls, uint32_t digest)
{
    if (!uart_ready) return;
    /* This also gives a readable startup failure if PLL switching failed. */
    SystemCoreClockUpdate();
    uint32_t prescaler = (RCC->CFGR >> 10) & 7u;
    uint32_t pclk = SystemCoreClock >> (prescaler < 4u ? 0u : prescaler - 3u);
    USART2->CR1 = 0;
    USART2->BRR = (pclk + 57600u) / 115200u;
    USART2->CR1 = USART_CR1_UE | USART_CR1_TE; /* 115200, 8N1, no RX/IRQ/DMA. */
    if (event[0] == 'B' && event[1] == 'O') {
        uint32_t apb2 = (RCC->CFGR >> 13) & 7u;
        uart_text("CONFIG board=NUCLEO-F446RE diagnostics=1 clock=HSI cpu_hz=");
        uart_unsigned(SystemCoreClock);
        uart_text(" pclk1_hz="); uart_unsigned(pclk);
        uart_text(" pclk2_hz=");
        uart_unsigned(SystemCoreClock >> (apb2 < 4u ? 0u : apb2 - 3u));
        uart_text(" idcode="); uart_hex(DBGMCU->IDCODE);
        uart_text(" flash_kib="); uart_unsigned(*(volatile const uint16_t *)FLASHSIZE_BASE);
        uart_text(" pllcfgr="); uart_hex(RCC->PLLCFGR);
        uart_text(" cfgr="); uart_hex(RCC->CFGR);
        uart_text(" cpacr="); uart_hex(SCB->CPACR);
        uart_text("\r\n");
    }
    uart_text("BENCH event="); uart_text(event);
    uart_text(" id="); uart_unsigned(id);
    uart_text(" calls="); uart_unsigned(calls);
    uart_text(" digest=");
    uart_hex(digest);
    uart_text("\r\n");
    while ((USART2->SR & USART_SR_TC) == 0) __NOP();
}
#endif

bool bench_platform_check(void)
{
    uint32_t pll_mask = RCC_PLLCFGR_PLLM | RCC_PLLCFGR_PLLN | RCC_PLLCFGR_PLLP |
        RCC_PLLCFGR_PLLSRC | RCC_PLLCFGR_PLLQ | RCC_PLLCFGR_PLLR;
    uint32_t bus_mask = RCC_CFGR_SWS | RCC_CFGR_HPRE | RCC_CFGR_PPRE1 | RCC_CFGR_PPRE2;
    return configured && (DBGMCU->IDCODE & 0xfffu) == 0x421u &&
        *(volatile const uint16_t *)FLASHSIZE_BASE == 512u &&
        (RCC->CR & (RCC_CR_HSIRDY | RCC_CR_PLLRDY | RCC_CR_HSEON)) ==
            (RCC_CR_HSIRDY | RCC_CR_PLLRDY) &&
        (RCC->CR & RCC_CR_HSITRIM) == RCC_CR_HSITRIM_4 &&
        (RCC->PLLCFGR & pll_mask) == PLL_CONFIG &&
        (RCC->CFGR & bus_mask) == (RCC_CFGR_SWS_PLL | BUS_CONFIG) &&
        (RCC->DCKCFGR & RCC_DCKCFGR_TIMPRE) == 0 &&
        (SCB->CPACR & FPU_ACCESS) == FPU_ACCESS &&
        (FLASH->ACR & FLASH_ACR_LATENCY) == FLASH_ACR_LATENCY_3WS &&
        (PWR->CR & (PWR_CR_VOS | PWR_CR_ODEN | PWR_CR_ODSWEN)) == PWR_CR_VOS &&
        (PWR->CSR & PWR_CSR_VOSRDY) != 0 &&
        (RCC->AHB2ENR & RCC_AHB2ENR_OTGFSEN) == 0 &&
        (RCC->AHB1ENR & (RCC_AHB1ENR_DMA1EN | RCC_AHB1ENR_DMA2EN |
            RCC_AHB1ENR_CRCEN | RCC_AHB1ENR_OTGHSEN)) == 0 &&
        (RCC->APB1ENR & RCC_APB1ENR_USART2EN) ==
            (BENCH_DIAGNOSTICS ? RCC_APB1ENR_USART2EN : 0u);
}

bool bench_platform_init(void)
{
    RCC->AHB1ENR |= RCC_AHB1ENR_GPIOAEN | RCC_AHB1ENR_GPIOCEN;
    (void)RCC->AHB1ENR;
    GPIOC->BSRR = 0xffu << 16;
    GPIOC->MODER = (GPIOC->MODER & ~0xffffu) | 0x5555u;
    GPIOC->OTYPER &= ~0xffu; GPIOC->OSPEEDR &= ~0xffffu; GPIOC->PUPDR &= ~0xffffu;
    GPIOA->BSRR = 1u << (5 + 16); /* Nucleo LD2, PA5 active-high: off. */
    GPIOA->MODER = (GPIOA->MODER & ~(3u << 10)) | (1u << 10);
    SysTick->CTRL = 0;
#if BENCH_DIAGNOSTICS
    diagnostic_uart_init();
#else
    RCC->APB1ENR &= ~RCC_APB1ENR_USART2EN;
    /* Both VCP pins are analog/high-impedance in measurement firmware. */
    GPIOA->MODER |= (3u << 4) | (3u << 6);
    GPIOA->PUPDR &= ~((3u << 4) | (3u << 6));
#endif
    if ((DBGMCU->IDCODE & 0xfffu) != 0x421u ||
        *(volatile const uint16_t *)FLASHSIZE_BASE != 512u) return false;
    RCC->CR = (RCC->CR & ~RCC_CR_HSITRIM) | RCC_CR_HSION | RCC_CR_HSITRIM_4;
    if (!wait_ready(&RCC->CR, RCC_CR_HSIRDY, RCC_CR_HSIRDY)) return false;
    RCC->CFGR &= ~RCC_CFGR_SW;
    if (!wait_ready(&RCC->CFGR, RCC_CFGR_SWS, RCC_CFGR_SWS_HSI)) return false;
    RCC->CR &= ~(RCC_CR_PLLON | RCC_CR_HSEON | RCC_CR_HSEBYP | RCC_CR_CSSON);
    if (!wait_ready(&RCC->CR, RCC_CR_PLLRDY, 0)) return false;
    RCC->APB1ENR |= RCC_APB1ENR_PWREN;
    (void)RCC->APB1ENR;
    PWR->CR = (PWR->CR & ~(PWR_CR_ODEN | PWR_CR_ODSWEN)) | PWR_CR_VOS;
    RCC->PLLCFGR = PLL_CONFIG;
    FLASH->ACR = FLASH_ACR_LATENCY_3WS | FLASH_ACR_PRFTEN | FLASH_ACR_ICEN | FLASH_ACR_DCEN;
    RCC->CFGR = (RCC->CFGR & ~(RCC_CFGR_HPRE | RCC_CFGR_PPRE1 | RCC_CFGR_PPRE2)) | BUS_CONFIG;
    RCC->DCKCFGR &= ~RCC_DCKCFGR_TIMPRE;
    RCC->CR |= RCC_CR_PLLON;
    if (!wait_ready(&RCC->CR, RCC_CR_PLLRDY, RCC_CR_PLLRDY) ||
        !wait_ready(&PWR->CSR, PWR_CSR_VOSRDY, PWR_CSR_VOSRDY)) return false;
    RCC->CFGR = (RCC->CFGR & ~RCC_CFGR_SW) | RCC_CFGR_SW_PLL;
    if (!wait_ready(&RCC->CFGR, RCC_CFGR_SWS, RCC_CFGR_SWS_PLL)) return false;
    SystemCoreClockUpdate();
    if (SystemCoreClock != BENCH_EXPECTED_CPU_HZ) return false;
    SCB->CPACR |= FPU_ACCESS;
    __DSB(); __ISB();
    volatile float a = 1.5f, b = 2.0f;
    volatile float result = a * b + 0.25f;
    if (result != 3.25f) return false;
    RCC->APB1ENR |= RCC_APB1ENR_TIM2EN;
    (void)RCC->APB1ENR;
    TIM2->CR1 = 0; TIM2->DIER = 0;
    TIM2->PSC = 4999u; /* APB1/4 x2=50 MHz ->10 kHz gap clock. */
    configured = true;
    return bench_platform_check();
}

void bench_platform_wait_ms(uint32_t milliseconds)
{
    while (milliseconds) {
        uint32_t chunk = milliseconds > 100000u ? 100000u : milliseconds;
        TIM2->CR1 = 0; TIM2->ARR = chunk * 10u - 1u; TIM2->CNT = 0;
        TIM2->EGR = TIM_EGR_UG; TIM2->SR = 0;
        TIM2->CR1 = TIM_CR1_OPM | TIM_CR1_CEN;
        while ((TIM2->SR & TIM_SR_UIF) == 0) __NOP();
        TIM2->CR1 = 0; TIM2->SR = 0;
        milliseconds -= chunk;
    }
}

void bench_platform_finish(void) { for (;;) __WFI(); }
static void fault_stop(void)
{
    bench_platform_signals(0, false, false, true, false);
    for (;;) __NOP();
}
void HardFault_Handler(void) { fault_stop(); }
void MemManage_Handler(void) { fault_stop(); }
void BusFault_Handler(void) { fault_stop(); }
void UsageFault_Handler(void) { fault_stop(); }
void NMI_Handler(void) { fault_stop(); }
int main(void) { bench_main(); bench_platform_finish(); return 0; }
