#!/usr/bin/python3

import sys
import time
import ctypes
import threading
from socket import inet_ntoa
from bcc import BPF
import numpy as np
import os
import pandas as pd
from joblib import load
from arithmetic_compression import AdaptiveArithmeticCodingFlows

# Files and model/scaler loading
MODEL_FILE = os.path.join("AI_training", "incremental_model.joblib")
SCALER_FILE = os.path.join("AI_training", "scaler.joblib")
PACKET_CAPTURE_FILE = os.path.join("kernel_space", "packet_capture.c")

clf = load(MODEL_FILE)

# Initialize the compression class
compression = AdaptiveArithmeticCodingFlows()

# Initialize accumulated data
accumulated_serialized_keys = []
accumulated_serialized_data = []
accumulated_key_frequencies = {}
accumulated_data_frequencies = {}

def preprocess_flow_for_ai(flow_data):
    """
    Aggregate and transform flow data from all CPUs into a single feature vector,
    then scale it using the saved scaler (SCALER_FILE).
    """
    total_packets = sum(cpu_data.packet_count for cpu_data in flow_data)
    total_byte_count = sum(cpu_data.byte_count for cpu_data in flow_data)
    fwd_packet_count = sum(cpu_data.fwd_packet_count for cpu_data in flow_data)
    bwd_packet_count = sum(cpu_data.bwd_packet_count for cpu_data in flow_data)
    fwd_byte_count = sum(cpu_data.fwd_byte_count for cpu_data in flow_data)
    bwd_byte_count = sum(cpu_data.bwd_byte_count for cpu_data in flow_data)
    valid_min_lengths = [cpu_data.min_packet_length for cpu_data in flow_data if cpu_data.min_packet_length is not None and cpu_data.min_packet_length > 0]
    min_packet_length = min(valid_min_lengths) if valid_min_lengths else 0
    max_packet_length = max(cpu_data.max_packet_length for cpu_data in flow_data)
    packet_length_square_sum = sum(cpu_data.packet_length_square_sum for cpu_data in flow_data)
    flow_duration = max(cpu_data.flow_duration for cpu_data in flow_data)
    flow_iat_total = sum(cpu_data.flow_iat_total for cpu_data in flow_data)
    valid_flow_iat_min = [cpu_data.flow_iat_min for cpu_data in flow_data if cpu_data.flow_iat_min is not None and cpu_data.flow_iat_min > 0]
    flow_iat_min = min(valid_flow_iat_min) if valid_flow_iat_min else 0
    flow_iat_max = max(cpu_data.flow_iat_max for cpu_data in flow_data)
    fwd_iat_total = sum(cpu_data.fwd_iat_total for cpu_data in flow_data)
    valid_fwd_iat_min = [cpu_data.fwd_iat_min for cpu_data in flow_data if cpu_data.fwd_iat_min is not None and cpu_data.fwd_iat_min > 0]
    fwd_iat_min = min(valid_fwd_iat_min) if valid_fwd_iat_min else 0
    fwd_iat_max = max(cpu_data.fwd_iat_max for cpu_data in flow_data)
    bwd_iat_total = sum(cpu_data.bwd_iat_total for cpu_data in flow_data)
    valid_bwd_iat_min = [cpu_data.bwd_iat_min for cpu_data in flow_data if cpu_data.bwd_iat_min is not None and cpu_data.bwd_iat_min > 0]
    bwd_iat_min = min(valid_bwd_iat_min) if valid_bwd_iat_min else 0
    bwd_iat_max = max(cpu_data.bwd_iat_max for cpu_data in flow_data)
    syn_count = sum(cpu_data.syn_count for cpu_data in flow_data)
    ack_count = sum(cpu_data.ack_count for cpu_data in flow_data)
    psh_count = sum(cpu_data.psh_count for cpu_data in flow_data)
    urg_count = sum(cpu_data.urg_count for cpu_data in flow_data)
    fin_count = sum(cpu_data.fin_count for cpu_data in flow_data)
    rst_count = sum(cpu_data.rst_count for cpu_data in flow_data)

    features = [
        total_packets,
        total_byte_count, 
        fwd_packet_count,
        bwd_packet_count,
        fwd_byte_count,
        bwd_byte_count,
        min_packet_length,
        max_packet_length,
        packet_length_square_sum,
        flow_duration,
        #flow_iat_total, #falta
        flow_iat_min,
        flow_iat_max,
        fwd_iat_total,
        fwd_iat_min,
        fwd_iat_max,
        bwd_iat_total,
        bwd_iat_min,
        bwd_iat_max,
        syn_count,
        ack_count,
        psh_count,
        urg_count,
        fin_count,
        rst_count
    ]

    column_names = [
        'Flow Duration',
        'Total Fwd Packets',
        'Total Backward Packets',
        'Flow Packets/s',
        'Flow Bytes/s',
        'Total Length of Fwd Packets',
        'Total Length of Bwd Packets',
        'Min Packet Length',
        'Max Packet Length',
        'Packet Length Variance',
        'Flow IAT Min',
        'Flow IAT Max',
        'Fwd IAT Total',
        'Fwd IAT Min',
        'Fwd IAT Max',
        'Bwd IAT Total',
        'Bwd IAT Min',
        'Bwd IAT Max',
        'SYN Flag Count',
        'ACK Flag Count',
        'PSH Flag Count',
        'URG Flag Count',
        'FIN Flag Count',
        'RST Flag Count',
    ]
    
    features_df = pd.DataFrame([features], columns=column_names)
    
    # Normalize and preprocess the features (ensure they match your training data format)
    scaler = load(SCALER_FILE) 
    features_scaled = scaler.transform(features_df)
    
    return features_scaled

def predict_flow_behavior(flow_data):
    """
    Use the trained model to predict whether the aggregated flow data
    indicates a benign flow or an anomaly.
    """
    features = preprocess_flow_for_ai(flow_data)
    prediction = clf.predict(features)
    
    return "BENIGN" if prediction == 1 else "ANOMALY DETECTED"

# Define ctypes structure for flow_key and flow_data
class FlowKey(ctypes.Structure):
    _fields_ = [
        ("src_ip", ctypes.c_uint32),
        ("dst_ip", ctypes.c_uint32),
        ("src_port", ctypes.c_uint16),
        ("dst_port", ctypes.c_uint16),
        ("protocol", ctypes.c_uint8)
    ]

class FlowData(ctypes.Structure):
    _fields_ = [
        ("first_seen", ctypes.c_uint64),
        ("last_seen", ctypes.c_uint64),
        ("packet_count", ctypes.c_uint32),
        ("byte_count", ctypes.c_uint64),          # Total bytes in the flow
        ("fwd_packet_count", ctypes.c_uint32),    # Packets from src to dst
        ("bwd_packet_count", ctypes.c_uint32),    # Packets from dst to src
        ("fwd_byte_count", ctypes.c_uint64),      # Bytes from src to dst
        ("bwd_byte_count", ctypes.c_uint64),      # Bytes from dst to src
        ("min_packet_length", ctypes.c_uint16),
        ("max_packet_length", ctypes.c_uint16),
        ("packet_length_square_sum", ctypes.c_uint64),  # Sum of packet lengths squared
        ("flow_duration", ctypes.c_uint64),             # Duration of the flow
        ("flow_iat_total", ctypes.c_uint64),            # Total inter-arrival time for flow
        ("flow_iat_min", ctypes.c_uint64),              # Min inter-arrival time for flow
        ("flow_iat_max", ctypes.c_uint64),              # Max inter-arrival time for flow
        ("fwd_iat_total", ctypes.c_uint64),             # Total inter-arrival time for forwarded packets
        ("fwd_iat_min", ctypes.c_uint64),               # Min inter-arrival time for forwarded packets
        ("fwd_iat_max", ctypes.c_uint64),               # Max inter-arrival time for forwarded packets
        ("bwd_iat_total", ctypes.c_uint64),             # Total inter-arrival time for backward packets
        ("bwd_iat_min", ctypes.c_uint64),               # Min inter-arrival time for backward packets
        ("bwd_iat_max", ctypes.c_uint64),               # Max inter-arrival time for backward packets
        ("syn_count", ctypes.c_uint32),
        ("ack_count", ctypes.c_uint32),
        ("psh_count", ctypes.c_uint32),
        ("urg_count", ctypes.c_uint32),
        ("fin_count", ctypes.c_uint32),                # FIN count
        ("rst_count", ctypes.c_uint32)                 # RST count
    ]

try:
    # Load the eBPF C code from file and attach the XDP hook
    with open(PACKET_CAPTURE_FILE, "r") as f:
        c_code = f.read()

    c_code = f"""{c_code}"""
    b = BPF(text=c_code)
    fn_capture_packet = b.load_func("capture_packet", BPF.XDP)
    b.attach_xdp(dev="enp0s8", fn=fn_capture_packet, flags=0)

    def getting_unupdated_flows(threshold_seconds=5, active_timeout=60):
        """
        Check flows in the 'flows' map. If a flow exceeds the idle or active timeout,
        move it to 'exported_flows' map, make a prediction, and compress anomaly data.
        """
        flows_map = b.get_table("flows")
        exported_flows_map = b.get_table("exported_flows")
        current_time_mcs = time.monotonic_ns() / 1000 
        print(f"Processing flows with idle_timeout={threshold_seconds}s and active_timeout={active_timeout}s:")

        for key, per_cpu_data in flows_map.items(): 
            # Temporary frequency tables for this batch
            key_frequencies = {}
            data_frequencies = {}

            src_ip = inet_ntoa(ctypes.c_uint32(key.src_ip).value.to_bytes(4, 'big'))
            dst_ip = inet_ntoa(ctypes.c_uint32(key.dst_ip).value.to_bytes(4, 'big'))

            # Collect per-flow information from all CPUs
            last_seen = max(cpu_data.last_seen for cpu_data in per_cpu_data)
            first_seen = min(cpu_data.first_seen for cpu_data in per_cpu_data if cpu_data.first_seen > 0)

            # Validate that `first_seen` makes sense
            if first_seen == 0 or first_seen > current_time_mcs:
                print(f"Warning: Invalid first_seen value for flow: src_ip={src_ip}, dst_ip={dst_ip}")
                continue

            # Calculate durations
            idle_duration = (current_time_mcs - last_seen) / 1e6
            active_duration = (current_time_mcs - first_seen) / 1e6

            # Check if the flow should be exported
            if idle_duration > threshold_seconds or active_duration > active_timeout:
                total_packets = sum(cpu_data.packet_count for cpu_data in per_cpu_data)
                total_byte_count = sum(cpu_data.byte_count for cpu_data in per_cpu_data)
                fwd_packet_count = sum(cpu_data.fwd_packet_count for cpu_data in per_cpu_data)
                bwd_packet_count = sum(cpu_data.bwd_packet_count for cpu_data in per_cpu_data)
                fwd_byte_count = sum(cpu_data.fwd_byte_count for cpu_data in per_cpu_data)
                bwd_byte_count = sum(cpu_data.bwd_byte_count for cpu_data in per_cpu_data)
                valid_min_lengths = [cpu_data.min_packet_length for cpu_data in per_cpu_data if cpu_data.min_packet_length is not None and cpu_data.min_packet_length > 0]
                min_packet_length = min(valid_min_lengths) if valid_min_lengths else 0
                max_packet_length = max(cpu_data.max_packet_length for cpu_data in per_cpu_data)
                packet_length_square_sum = sum(cpu_data.packet_length_square_sum for cpu_data in per_cpu_data)
                flow_duration = max(cpu_data.flow_duration for cpu_data in per_cpu_data)
                flow_iat_total = sum(cpu_data.flow_iat_total for cpu_data in per_cpu_data)
                valid_flow_iat_min = [cpu_data.flow_iat_min for cpu_data in per_cpu_data if cpu_data.flow_iat_min is not None and cpu_data.flow_iat_min > 0]
                flow_iat_min = min(valid_flow_iat_min) if valid_flow_iat_min else 0
                flow_iat_max = max(cpu_data.flow_iat_max for cpu_data in per_cpu_data)
                fwd_iat_total = sum(cpu_data.fwd_iat_total for cpu_data in per_cpu_data)
                valid_fwd_iat_min = [cpu_data.fwd_iat_min for cpu_data in per_cpu_data if cpu_data.fwd_iat_min is not None and cpu_data.fwd_iat_min > 0]
                fwd_iat_min = min(valid_fwd_iat_min) if valid_fwd_iat_min else 0
                fwd_iat_max = max(cpu_data.fwd_iat_max for cpu_data in per_cpu_data)
                bwd_iat_total = sum(cpu_data.bwd_iat_total for cpu_data in per_cpu_data)
                valid_bwd_iat_min = [cpu_data.bwd_iat_min for cpu_data in per_cpu_data if cpu_data.bwd_iat_min is not None and cpu_data.bwd_iat_min > 0]
                bwd_iat_min = min(valid_bwd_iat_min) if valid_bwd_iat_min else 0
                bwd_iat_max = max(cpu_data.bwd_iat_max for cpu_data in per_cpu_data)
                syn_count = sum(cpu_data.syn_count for cpu_data in per_cpu_data)
                ack_count = sum(cpu_data.ack_count for cpu_data in per_cpu_data)
                psh_count = sum(cpu_data.psh_count for cpu_data in per_cpu_data)
                urg_count = sum(cpu_data.urg_count for cpu_data in per_cpu_data)
                fin_count = sum(cpu_data.fin_count for cpu_data in per_cpu_data)
                rst_count = sum(cpu_data.rst_count for cpu_data in per_cpu_data)

                # Export the flow and remove from the flows map
                flow_data = FlowData(
                    first_seen=first_seen,
                    last_seen=last_seen,
                    packet_count=total_packets,
                    byte_count=total_byte_count,
                    fwd_packet_count=fwd_packet_count,
                    bwd_packet_count=bwd_packet_count,
                    fwd_byte_count=fwd_byte_count,
                    bwd_byte_count=bwd_byte_count,
                    min_packet_length=min_packet_length,
                    max_packet_length=max_packet_length,
                    packet_length_square_sum=packet_length_square_sum,
                    flow_duration=flow_duration,
                    flow_iat_total=flow_iat_total,
                    flow_iat_min=flow_iat_min,
                    flow_iat_max=flow_iat_max,
                    fwd_iat_total=fwd_iat_total,
                    fwd_iat_min=fwd_iat_min,
                    fwd_iat_max=fwd_iat_max,
                    bwd_iat_total=bwd_iat_total,
                    bwd_iat_min=bwd_iat_min,
                    bwd_iat_max=bwd_iat_max,
                    syn_count=syn_count,
                    ack_count=ack_count,
                    psh_count=psh_count,
                    urg_count=urg_count,
                    fin_count=fin_count,
                    rst_count=rst_count,
                    idle_duration=idle_duration,
                    active_duration=active_duration
                )
                exported_flows_map[key] = flow_data

                prediction = predict_flow_behavior(exported_flows_map[key])
                src_ip = inet_ntoa(ctypes.c_uint32(key.src_ip).value.to_bytes(4, 'big'))
                dst_ip = inet_ntoa(ctypes.c_uint32(key.dst_ip).value.to_bytes(4, 'big'))
                print(f"Flow from {src_ip} to {dst_ip} is: {prediction}")
                if prediction == "ANOMALY DETECTED":
                    print(f"ALERT: Anomalous flow detected from {src_ip} to {dst_ip}!")

                    flow_key = FlowKey(key.src_ip, key.dst_ip, key.src_port, key.dst_port, key.protocol)

                    # Serialize the FlowKey and FlowData for compression
                    serialized_key = tuple(compression._serialize_flow_key(flow_key))
                    serialized_flow_data = tuple(compression._serialize_flow_data(flow_data))

                    # Update frequency tables for FlowKey and FlowData
                    compression.update_frequencies(serialized_key, key_frequencies)
                    compression.update_frequencies(serialized_flow_data, data_frequencies)

                    # Append to the list of serialized data
                    accumulated_serialized_keys.append(serialized_key)
                    accumulated_serialized_data.append(serialized_flow_data)

                    # Update global frequency tables
                    for k, v in key_frequencies.items():
                        accumulated_key_frequencies[k] = accumulated_key_frequencies.get(k, 0) + v
                    for k, v in data_frequencies.items():
                        accumulated_data_frequencies[k] = accumulated_data_frequencies.get(k, 0) + v

                    else:
                        print(f"Flow from {src_ip} to {dst_ip} is: {prediction}")

                else:
                    print(f"Flow from {src_ip} to {dst_ip} is: {prediction}")
                    del exported_flows_map[key]  # Remove normal flow from map
                del flows_map[key]  # Remove flow from map
        
        if not accumulated_serialized_keys and not accumulated_serialized_data:
            print("No data to compress.")
            return
        
        key_probs = compression.calculate_probabilities(accumulated_key_frequencies)
        data_probs = compression.calculate_probabilities(accumulated_data_frequencies)

        # Codificar las claves y los datos usando la función encode
        encoded_keys = compression.encode(accumulated_serialized_keys, key_probs)
        encoded_data = compression.encode(accumulated_serialized_data, data_probs)

        # Guardar los datos comprimidos en un archivo binario
        filename = "compressed_flows.dat"
        compression.save_to_file(filename, encoded_keys, encoded_data, accumulated_serialized_keys, accumulated_serialized_data, key_probs, data_probs)
        print("File succesfully compressed")

        # Clear accumulated data
        accumulated_serialized_keys.clear()
        accumulated_serialized_data.clear()
        accumulated_key_frequencies.clear()
        accumulated_data_frequencies.clear()

    def periodic_print_flows(interval):
        """
        Periodically call export_expired_flows() to check and handle flows.
        """
        def print_and_reschedule():
            getting_unupdated_flows()
            threading.Timer(interval, print_and_reschedule).start()

        print_and_reschedule()

    # Prompt the user for a sampling rate and update the eBPF map
    input_value = b.get_table("input_value")
    key = 0
    new_value = input("Enter a packet sampling rate in % (0-100):\n")
    try:
        # Try to convert input to integer and ensure it falls within the valid range
        new_value = int(new_value)
        
        if 0 <= new_value <= 100:
            # Update the value at the given key/index
            key_ctypes = ctypes.c_uint32(0)
            new_value_ctypes = ctypes.c_uint32(new_value) # packet sample rate
            
            # Update the map element using the proper ctypes instances
            input_value[key_ctypes] = new_value_ctypes
            print(f"Updated sampling rate to {new_value}%")
        else:
            print("Error: Please enter a value between 0 and 100.")
    
    except ValueError:
        print("Error: Please enter a valid integer value.")
        
    periodic_print_flows(1)

except KeyboardInterrupt:
    b.remove_xdp(dev="enp0s8", flags=0)
    sys.exit()