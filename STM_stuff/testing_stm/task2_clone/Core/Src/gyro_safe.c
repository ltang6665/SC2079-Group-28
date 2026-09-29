#include "gyro_safe.h"

#include "cmsis_os.h"
#include <stddef.h>

#define ICM20948_ADDRESS_7BIT       0x68U
#define ICM20948_WHO_AM_I_REG       0x00U
#define ICM20948_WHO_AM_I_VALUE     0xEAU
#define ICM20948_BANK_SEL_REG       0x7FU
#define ICM20948_PWR_MGMT_1_REG     0x06U
#define ICM20948_PWR_MGMT_2_REG     0x07U
#define ICM20948_LP_CONFIG_REG      0x05U
#define ICM20948_GYRO_ZOUT_H_REG    0x37U
#define ICM20948_GYRO_SMPLRT_REG    0x00U
#define ICM20948_GYRO_CONFIG_1_REG  0x01U

#define ICM20948_I2C_TIMEOUT_MS     3U
#define ICM20948_LSB_PER_DPS        16.4f

/* Board mapping from HAL_I2C_MspInit: I2C2 on PB10 (SCL), PB11 (SDA).
 * Keep the existing external pull-ups; do not add pull-ups to another rail.
 * Recovery is called only by gyroTask, with the scheduler running and no
 * other task/ISR using this I2C peripheral. It is not an ISR-safe function.
 */
#define GYRO_I2C_PORT               GPIOB
#define GYRO_I2C_SCL_PIN            GPIO_PIN_10
#define GYRO_I2C_SDA_PIN            GPIO_PIN_11
#define GYRO_I2C_PINS               (GYRO_I2C_SCL_PIN | GYRO_I2C_SDA_PIN)
#define GYRO_I2C_LINE_TIMEOUT_MS    5U
#define GYRO_I2C_EDGE_DELAY_MS      2U
#define GYRO_I2C_CLEAR_CLOCKS       9U


static bool i2c2_pins_match_board(void)
{
    /* Refuse to pulse unrelated pins if the CubeMX mapping has changed.
     * PB10/PB11 must currently be alternate-function, open-drain, AF4.
     * MODER has two bits per pin; AFR[1] covers pins 8 through 15.
     */
    const uint32_t mode_mask = (3UL << 20) | (3UL << 22);
    const uint32_t mode_af = (2UL << 20) | (2UL << 22);
    const uint32_t af_mask = (15UL << 8) | (15UL << 12);
    const uint32_t af_i2c2 = ((uint32_t)GPIO_AF4_I2C2 << 8) |
                             ((uint32_t)GPIO_AF4_I2C2 << 12);

    return __HAL_RCC_GPIOB_IS_CLK_ENABLED() &&
           (GYRO_I2C_PORT->MODER & mode_mask) == mode_af &&
           (GYRO_I2C_PORT->OTYPER & GYRO_I2C_PINS) == GYRO_I2C_PINS &&
           (GYRO_I2C_PORT->AFR[1] & af_mask) == af_i2c2;
}


static bool i2c2_wait_high(uint16_t pin)
{
    const uint32_t start = HAL_GetTick();

    while (HAL_GPIO_ReadPin(GYRO_I2C_PORT, pin) != GPIO_PIN_SET)
    {
        /* Unsigned subtraction remains valid when the millisecond tick wraps. */
        if ((uint32_t)(HAL_GetTick() - start) >= GYRO_I2C_LINE_TIMEOUT_MS)
        {
            return false;
        }
        osDelay(1U);
    }

    return true;
}


static bool i2c2_clear_bus(void)
{
    GPIO_InitTypeDef pins = {0};
    bool cleared = false;

    /* HAL_I2C_DeInit has disabled I2C2 and detached its pins by this point.
     * Preload released levels before enabling GPIO output mode.
     * In open-drain mode SET releases the wire; it does not drive it high.
     */
    __HAL_RCC_GPIOB_CLK_ENABLE();
    HAL_GPIO_WritePin(GYRO_I2C_PORT, GYRO_I2C_PINS, GPIO_PIN_SET);
    pins.Pin = GYRO_I2C_PINS;
    pins.Mode = GPIO_MODE_OUTPUT_OD;
    pins.Pull = GPIO_NOPULL;
    pins.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GYRO_I2C_PORT, &pins);
    osDelay(GYRO_I2C_EDGE_DELAY_MS);

    /* A device holding SCL low prevents clocking; fail after a bounded wait. */
    if (!i2c2_wait_high(GYRO_I2C_SCL_PIN))
    {
        goto release_lines;
    }

    /* Let an interrupted target finish its byte and release SDA.
     * Stop early if SDA is already released. These are recovery clocks,
     * not normal sensor traffic; the slow edges allow other tasks to run.
     */
    for (uint32_t pulse = 0U;
         pulse < GYRO_I2C_CLEAR_CLOCKS &&
         HAL_GPIO_ReadPin(GYRO_I2C_PORT, GYRO_I2C_SDA_PIN) == GPIO_PIN_RESET;
         ++pulse)
    {
        HAL_GPIO_WritePin(GYRO_I2C_PORT, GYRO_I2C_SCL_PIN, GPIO_PIN_RESET);
        osDelay(GYRO_I2C_EDGE_DELAY_MS);
        HAL_GPIO_WritePin(GYRO_I2C_PORT, GYRO_I2C_SCL_PIN, GPIO_PIN_SET);
        if (!i2c2_wait_high(GYRO_I2C_SCL_PIN))
        {
            goto release_lines;
        }
        osDelay(GYRO_I2C_EDGE_DELAY_MS);
    }

    if (!i2c2_wait_high(GYRO_I2C_SDA_PIN))
    {
        goto release_lines;
    }

    /* Generate STOP: prepare SDA low while SCL is low, release SCL,
     * then release SDA while SCL is high. Never actively drive either high.
     */
    HAL_GPIO_WritePin(GYRO_I2C_PORT, GYRO_I2C_SCL_PIN, GPIO_PIN_RESET);
    osDelay(GYRO_I2C_EDGE_DELAY_MS);
    HAL_GPIO_WritePin(GYRO_I2C_PORT, GYRO_I2C_SDA_PIN, GPIO_PIN_RESET);
    osDelay(GYRO_I2C_EDGE_DELAY_MS);
    HAL_GPIO_WritePin(GYRO_I2C_PORT, GYRO_I2C_SCL_PIN, GPIO_PIN_SET);
    if (!i2c2_wait_high(GYRO_I2C_SCL_PIN))
    {
        goto release_lines;
    }
    osDelay(GYRO_I2C_EDGE_DELAY_MS);
    HAL_GPIO_WritePin(GYRO_I2C_PORT, GYRO_I2C_SDA_PIN, GPIO_PIN_SET);
    osDelay(GYRO_I2C_EDGE_DELAY_MS);

    cleared = i2c2_wait_high(GYRO_I2C_SDA_PIN) &&
              HAL_GPIO_ReadPin(GYRO_I2C_PORT, GYRO_I2C_SCL_PIN) == GPIO_PIN_SET;

release_lines:
    /* On every exit release both GPIO outputs. Recover restores AF mode. */
    HAL_GPIO_WritePin(GYRO_I2C_PORT, GYRO_I2C_PINS, GPIO_PIN_SET);
    return cleared;
}


static bool write_reg(GyroSafe *gyro, uint8_t reg, uint8_t value)
{
    if (gyro == NULL || gyro->i2c == NULL)
    {
        return false;
    }

    return HAL_I2C_Mem_Write(
               gyro->i2c,
               ICM20948_ADDRESS_7BIT << 1,
               reg,
               I2C_MEMADD_SIZE_8BIT,
               &value,
               1U,
               ICM20948_I2C_TIMEOUT_MS
           ) == HAL_OK;
}


static bool read_regs(GyroSafe *gyro, uint8_t reg, uint8_t *data, uint16_t size)
{
    if (gyro == NULL || gyro->i2c == NULL || data == NULL || size == 0U)
    {
        return false;
    }

    return HAL_I2C_Mem_Read(
               gyro->i2c,
               ICM20948_ADDRESS_7BIT << 1,
               reg,
               I2C_MEMADD_SIZE_8BIT,
               data,
               size,
               ICM20948_I2C_TIMEOUT_MS
           ) == HAL_OK;
}


static bool select_bank(GyroSafe *gyro, uint8_t bank)
{
    return write_reg(gyro, ICM20948_BANK_SEL_REG, (uint8_t)(bank << 4));
}


static bool read_raw_z(GyroSafe *gyro, int16_t *raw_z)
{
    uint8_t bytes[2];

    if (raw_z == NULL || !read_regs(gyro, ICM20948_GYRO_ZOUT_H_REG, bytes, 2U))
    {
        return false;
    }

    *raw_z = (int16_t)(((uint16_t)bytes[0] << 8) | bytes[1]);
    return true;
}


bool GyroSafe_Init(GyroSafe *gyro, I2C_HandleTypeDef *i2c)
{
    uint8_t identity = 0U;

    if (gyro == NULL || i2c == NULL)
    {
        return false;
    }

    gyro->i2c = i2c;
    gyro->bias_raw = 0.0f;

    /* Return to bank 0, reset the device, and allow it to restart. */
    if (!select_bank(gyro, 0U) ||
        !write_reg(gyro, ICM20948_PWR_MGMT_1_REG, 0x80U))
    {
        return false;
    }
    osDelay(100U);

    if (!select_bank(gyro, 0U) ||
        !read_regs(gyro, ICM20948_WHO_AM_I_REG, &identity, 1U) ||
        identity != ICM20948_WHO_AM_I_VALUE)
    {
        return false;
    }

    /* PLL clock, no sleep/cycling, all accelerometer/gyro axes enabled. */
    if (!write_reg(gyro, ICM20948_PWR_MGMT_1_REG, 0x01U) ||
        !write_reg(gyro, ICM20948_PWR_MGMT_2_REG, 0x00U) ||
        !write_reg(gyro, ICM20948_LP_CONFIG_REG, 0x00U))
    {
        return false;
    }

    /* Bank 2: retain the project's 16.4 LSB/(degree/s) and LPF settings. */
    if (!select_bank(gyro, 2U) ||
        !write_reg(gyro, ICM20948_GYRO_SMPLRT_REG, 0x11U) ||
        !write_reg(gyro, ICM20948_GYRO_CONFIG_1_REG, 0x2FU) ||
        !select_bank(gyro, 0U))
    {
        return false;
    }

    osDelay(20U);
    return true;
}


bool GyroSafe_Recover(GyroSafe *gyro, I2C_HandleTypeDef *i2c)
{
    if (gyro == NULL || i2c == NULL || i2c->Instance != I2C2)
    {
        return false;
    }

    if (!i2c2_pins_match_board())
    {
        return false;
    }

    if (HAL_I2C_DeInit(i2c) != HAL_OK)
    {
        return false;
    }

    const bool bus_cleared = i2c2_clear_bus();

    /* Reset the STM32 peripheral separately from clearing the physical bus.
     * RCC reset does not reset or remove power from the external gyro.
     */
    __HAL_RCC_I2C2_CLK_ENABLE();
    __HAL_RCC_I2C2_FORCE_RESET();
    osDelay(1U);
    __HAL_RCC_I2C2_RELEASE_RESET();
    osDelay(1U);

    /* DeInit set the HAL state to RESET, so Init calls HAL_I2C_MspInit and
     * restores PB10/PB11 to AF4 open-drain, even after a failed bus clear.
     * Do not short-circuit this call on bus_cleared: pins must be restored.
     */
    if (HAL_I2C_Init(i2c) != HAL_OK)
    {
        return false;
    }

    if (!bus_cleared)
    {
        return false;
    }

    /* The existing sensor soft reset, WHO_AM_I check and setup follow.
     * gyroTask performs its existing stationary calibration afterwards.
     */
    return GyroSafe_Init(gyro, i2c);
}


bool GyroSafe_Calibrate(GyroSafe *gyro, uint16_t samples, uint32_t period_ms)
{
    int64_t sum = 0;

    if (gyro == NULL || samples == 0U)
    {
        return false;
    }

    for (uint16_t index = 0U; index < samples; ++index)
    {
        int16_t raw_z;

        osDelay(period_ms);
        if (!read_raw_z(gyro, &raw_z))
        {
            return false;
        }
        sum += raw_z;
    }

    gyro->bias_raw = (float)sum / (float)samples;
    return true;
}


bool GyroSafe_ReadRateDps(GyroSafe *gyro, float scale_trim, float *rate_dps)
{
    int16_t raw_z;

    if (rate_dps == NULL || !read_raw_z(gyro, &raw_z))
    {
        return false;
    }

    *rate_dps = (((float)raw_z - gyro->bias_raw) / ICM20948_LSB_PER_DPS) *
                scale_trim;
    return true;
}
