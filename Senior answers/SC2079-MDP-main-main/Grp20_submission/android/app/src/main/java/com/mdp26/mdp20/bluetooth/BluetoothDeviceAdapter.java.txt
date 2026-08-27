package com.mdp26.mdp20.bluetooth;

import android.annotation.SuppressLint;
import android.bluetooth.BluetoothDevice;
import android.content.Context;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.recyclerview.widget.RecyclerView;

import com.mdp26.mdp20.R;

import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.function.Consumer;

public class BluetoothDeviceAdapter extends RecyclerView.Adapter<RecyclerView.ViewHolder> {
    private static final int TYPE_HEADER = 0;
    private static final int TYPE_DEVICE = 1;

    private final List<Object> items = new ArrayList<>();
    private final List<BluetoothDeviceModel> bondedList = new ArrayList<>();
    private final List<BluetoothDeviceModel> discoveredList = new ArrayList<>();
    
    private Context context;
    private Consumer<BluetoothDeviceModel> onClickBtDevice;

    public BluetoothDeviceAdapter(Context context, List<BluetoothDeviceModel> ignoredInitialList, Consumer<BluetoothDeviceModel> onClickBtDevice) {
        this.context = context;
        this.onClickBtDevice = onClickBtDevice;
        
    }

    @Override
    public int getItemViewType(int position) {
        if (items.get(position) instanceof String) {
            return TYPE_HEADER;
        }
        return TYPE_DEVICE;
    }

    @NonNull
    @Override
    public RecyclerView.ViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        if (viewType == TYPE_HEADER) {
            View view = LayoutInflater.from(context).inflate(R.layout.item_bluetooth_header, parent, false);
            return new HeaderViewHolder(view);
        } else {
            View view = LayoutInflater.from(context).inflate(R.layout.item_bluetooth_device, parent, false);
            return new DeviceViewHolder(view);
        }
    }

    @Override
    public void onBindViewHolder(@NonNull RecyclerView.ViewHolder holder, int position) {
        if (getItemViewType(position) == TYPE_HEADER) {
            String title = (String) items.get(position);
            ((HeaderViewHolder) holder).title.setText(title);
        } else {
            BluetoothDeviceModel device = (BluetoothDeviceModel) items.get(position);
            DeviceViewHolder deviceHolder = (DeviceViewHolder) holder;

            deviceHolder.deviceName.setText(device.name() != null ? device.name() : "Unknown Device");
            deviceHolder.deviceAddress.setText(device.address());

            if (device.hasBond()) {
                deviceHolder.pairedStatus.setText("PAIRED");
                deviceHolder.pairedStatus.setVisibility(View.VISIBLE);
            } else {
                deviceHolder.pairedStatus.setVisibility(View.GONE);
            }

            deviceHolder.itemView.setOnClickListener(v -> {
                if (onClickBtDevice != null) {
                    onClickBtDevice.accept(device);
                }
            });
        }
    }

    @Override
    public int getItemCount() {
        return items.size();
    }

    private void rebuildList() {
        items.clear();
        
        if (!bondedList.isEmpty()) {
            items.add("Paired Devices");
            items.addAll(bondedList);
        }

        if (!discoveredList.isEmpty()) {
            items.add("Available Devices");
            items.addAll(discoveredList);
        } else if (bondedList.isEmpty()) {
            
        }
        
        notifyDataSetChanged();
    }

    @SuppressLint({"MissingPermission", "NotifyDataSetChanged"})
    public void initPairedDevices(Collection<BluetoothDevice> devices) {
        bondedList.clear();
        for (BluetoothDevice device : devices) {
            bondedList.add(new BluetoothDeviceModel(
                    device,
                    device.getName(),
                    device.getAddress(),
                    true
            ));
        }
        rebuildList();
    }

    @SuppressLint({"MissingPermission"})
    public void addDiscoveredDevice(BluetoothDevice bluetoothDevice) {
        
        for (BluetoothDeviceModel existing : discoveredList) {
            if (existing.address().equals(bluetoothDevice.getAddress())) return;
        }
        
        for (BluetoothDeviceModel paired : bondedList) {
            if (paired.address().equals(bluetoothDevice.getAddress())) return; 
        }

        discoveredList.add(new BluetoothDeviceModel(
                bluetoothDevice,
                bluetoothDevice.getName(),
                bluetoothDevice.getAddress(),
                false
        ));
        rebuildList();
    }
    
    public static class HeaderViewHolder extends RecyclerView.ViewHolder {
        TextView title;
        public HeaderViewHolder(@NonNull View itemView) {
            super(itemView);
            title = itemView.findViewById(R.id.headerTitle);
        }
    }

    public static class DeviceViewHolder extends RecyclerView.ViewHolder {
        TextView deviceName;
        TextView deviceAddress;
        TextView pairedStatus;

        public DeviceViewHolder(@NonNull View itemView) {
            super(itemView);
            deviceName = itemView.findViewById(R.id.deviceName);
            deviceAddress = itemView.findViewById(R.id.deviceAddress);
            pairedStatus = itemView.findViewById(R.id.pairedStatus);
        }
    }
}
