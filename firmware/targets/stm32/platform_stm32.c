#include "bench_platform.h"
#include "bench_config.h"
#include "stm32f4xx.h"

#if !defined(__ARM_FP) || ((__ARM_FP & 4) == 0) || defined(__SOFTFP__)
#error "STM32 benchmark requires hard-float single-precision FPU code"
#endif
#if HSE_VALUE != 25000000U
#error "This profile is for a physically verified 25 MHz HSE Black Pill"
#endif

static bool configured;
_Static_assert(BENCH_EXPECTED_CPU_HZ == 100000000u, "CPU profile mismatch");
_Static_assert(BENCH_PIN_RUN == 0 && BENCH_PIN_ID0 == 1 && BENCH_PIN_ID1 == 2 &&
    BENCH_PIN_ID2 == 3 && BENCH_PIN_ID3 == 4 && BENCH_PIN_IDLE == 5 &&
    BENCH_PIN_ERROR == 6 && BENCH_PIN_DONE == 7, "STM32 PA0..PA7 signal map required");
#define PLL_CONFIG (25u | (200u << 6) | RCC_PLLCFGR_PLLSRC_HSE | (5u << 24))
#define FPU_ACCESS (0xfu << 20)

void bench_platform_signals(unsigned id, bool run, bool idle, bool error, bool done)
{
    GPIOA->BSRR = 1u << 16; /* RUN low before changing identity. */
    uint32_t bits = ((id & 15u) << 1) | ((uint32_t)idle << 5) |
        ((uint32_t)error << 6) | ((uint32_t)done << 7);
    GPIOA->BSRR = ((~bits & 0xffu) << 16) | bits;
    __DMB();
    if (run) GPIOA->BSRR = 1u;
}

static bool wait_ready(volatile uint32_t *reg, uint32_t mask, uint32_t expected)
{
    /* Bounded startup poll, not a time measurement. A failure prevents RUN. */
    for (uint32_t attempts = 0; attempts < 4000000u; ++attempts)
        if ((*reg & mask) == expected) return true;
    return false;
}

bool bench_platform_check(void)
{
    uint32_t pll_mask = RCC_PLLCFGR_PLLM | RCC_PLLCFGR_PLLN | RCC_PLLCFGR_PLLP |
        RCC_PLLCFGR_PLLSRC | RCC_PLLCFGR_PLLQ;
    uint32_t bus_mask = RCC_CFGR_SWS | RCC_CFGR_HPRE | RCC_CFGR_PPRE1 | RCC_CFGR_PPRE2;
    return configured && (RCC->CR & (RCC_CR_HSERDY | RCC_CR_PLLRDY)) ==
        (RCC_CR_HSERDY | RCC_CR_PLLRDY) && (RCC->PLLCFGR & pll_mask) == PLL_CONFIG &&
        (RCC->CFGR & bus_mask) == (RCC_CFGR_SWS_PLL | RCC_CFGR_PPRE1_DIV2) &&
        (SCB->CPACR & FPU_ACCESS) == FPU_ACCESS &&
        (FLASH->ACR & FLASH_ACR_LATENCY) == FLASH_ACR_LATENCY_3WS &&
        (PWR->CR & PWR_CR_VOS) == PWR_CR_VOS &&
        (PWR->CSR & PWR_CSR_VOSRDY) != 0 &&
        (RCC->AHB2ENR & RCC_AHB2ENR_OTGFSEN) == 0 &&
        (RCC->AHB1ENR & (RCC_AHB1ENR_DMA1EN | RCC_AHB1ENR_DMA2EN | RCC_AHB1ENR_CRCEN)) == 0;
}

bool bench_platform_init(void)
{
    RCC->AHB1ENR |= RCC_AHB1ENR_GPIOAEN | RCC_AHB1ENR_GPIOCEN;
    (void)RCC->AHB1ENR;
    GPIOA->BSRR = 0xffu << 16;
    GPIOA->MODER = (GPIOA->MODER & ~0xffffu) | 0x5555u;
    GPIOA->OTYPER &= ~0xffu; GPIOA->OSPEEDR &= ~0xffffu; GPIOA->PUPDR &= ~0xffffu;
    GPIOC->BSRR = 1u << 13; /* PC13 onboard LED is active-low: off. */
    GPIOC->MODER = (GPIOC->MODER & ~(3u << 26)) | (1u << 26);
    SysTick->CTRL = 0; /* No periodic framework tick in this CMSIS-only target. */
    RCC->APB1ENR |= RCC_APB1ENR_PWREN;
    (void)RCC->APB1ENR;
    PWR->CR |= PWR_CR_VOS; /* Scale 1, required by this 100 MHz profile. */
    RCC->CR |= RCC_CR_HSEON;
    if (!wait_ready(&RCC->CR, RCC_CR_HSERDY, RCC_CR_HSERDY)) return false;
    RCC->CR &= ~RCC_CR_PLLON;
    if (!wait_ready(&RCC->CR, RCC_CR_PLLRDY, 0)) return false;
    RCC->PLLCFGR = PLL_CONFIG;
    FLASH->ACR = FLASH_ACR_LATENCY_3WS | FLASH_ACR_PRFTEN | FLASH_ACR_ICEN | FLASH_ACR_DCEN;
    RCC->CFGR = (RCC->CFGR & ~(RCC_CFGR_HPRE | RCC_CFGR_PPRE1 | RCC_CFGR_PPRE2)) |
        RCC_CFGR_PPRE1_DIV2;
    RCC->CR |= RCC_CR_PLLON;
    if (!wait_ready(&RCC->CR, RCC_CR_PLLRDY, RCC_CR_PLLRDY)) return false;
    /* F411 applies the requested voltage scale only with PLL enabled. */
    if (!wait_ready(&PWR->CSR, PWR_CSR_VOSRDY, PWR_CSR_VOSRDY)) return false;
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
    TIM2->PSC = 9999u; /* APB1 timer clock=100 MHz -> control clock=10 kHz. */
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

void bench_platform_finish(void)
{
    for (;;) __WFI();
}

/* Turn a CPU fault into an invalid sequence, never an apparently completed RUN. */
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

int main(void)
{
    bench_main();
    bench_platform_finish();
    return 0;
}
