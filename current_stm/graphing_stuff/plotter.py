import csv
import matplotlib.pyplot as plt

def main():
    times, a_vals, b_vals = [], [], []
    
    # Read the CSV transferred from the Pi
    try:
        with open('motor_log.csv', 'r') as f:
            reader = csv.reader(f)
            next(reader) # Skip header
            for row in reader:
                times.append(float(row[0]))
                a_vals.append(int(row[1]))
                b_vals.append(int(row[2]))
    except FileNotFoundError:
        print("Error: 'motor_log.csv' not found. Ensure you transferred it from the Pi.")
        return

    # Plot the results
    plt.figure(figsize=(10, 5))
    plt.plot(times, a_vals, label='Motor A (Left)', alpha=0.8, linewidth=2)
    plt.plot(times, b_vals, label='Motor B (Right)', alpha=0.8, linewidth=2)
    
    plt.title('Motor Acceleration Profile (Step Response)')
    plt.xlabel('Time (seconds)')
    plt.ylabel('Speed (Encoder Deltas / 20ms)')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

if __name__ == '__main__':
    main()