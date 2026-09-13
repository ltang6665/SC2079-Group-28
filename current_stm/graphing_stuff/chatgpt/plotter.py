import csv
import matplotlib.pyplot as plt


SAMPLE_PERIOD = 0.020


def main():

    times = []
    a_vals = []
    b_vals = []

    try:
        with open('motor_log.csv', 'r') as f:

            reader = csv.reader(f)
            next(reader)

            for row in reader:

                times.append(float(row[0]))
                a_vals.append(int(row[1]))
                b_vals.append(int(row[2]))

    except FileNotFoundError:

        print(
            "Error: motor_log.csv not found."
        )

        return


    # -----------------------------
    # Calculate acceleration
    # -----------------------------

    a_accel = [0.0]
    b_accel = [0.0]

    for i in range(1, len(a_vals)):

        a_accel.append(
            (a_vals[i] - a_vals[i - 1])
            / SAMPLE_PERIOD
        )

        b_accel.append(
            (b_vals[i] - b_vals[i - 1])
            / SAMPLE_PERIOD
        )


    # -----------------------------
    # Plot wheel speed
    # -----------------------------

    plt.figure(figsize=(10, 5))

    plt.plot(
        times,
        a_vals,
        label='Motor A (Left)',
        linewidth=2
    )

    plt.plot(
        times,
        b_vals,
        label='Motor B (Right)',
        linewidth=2
    )

    plt.title(
        'Wheel Speed — Encoder Step Response'
    )

    plt.xlabel('Time (seconds)')
    plt.ylabel(
        'Encoder Counts / 20 ms'
    )

    plt.legend()
    plt.grid(True)
    plt.tight_layout()

    plt.show()


    # -----------------------------
    # Plot acceleration
    # -----------------------------

    plt.figure(figsize=(10, 5))

    plt.plot(
        times,
        a_accel,
        label='Motor A acceleration',
        linewidth=2
    )

    plt.plot(
        times,
        b_accel,
        label='Motor B acceleration',
        linewidth=2
    )

    plt.title(
        'Wheel Acceleration'
    )

    plt.xlabel('Time (seconds)')

    plt.ylabel(
        'Encoder-count units / s²'
    )

    plt.legend()
    plt.grid(True)
    plt.tight_layout()

    plt.show()


if __name__ == '__main__':
    main()