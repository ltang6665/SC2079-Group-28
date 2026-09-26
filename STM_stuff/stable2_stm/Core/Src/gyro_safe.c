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
    if (gyro == NULL || i2c == NULL)
    {
        return false;
    }

    (void)HAL_I2C_DeInit(i2c);
    osDelay(5U);

    if (HAL_I2C_Init(i2c) != HAL_OK)
    {
        return false;
    }

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
