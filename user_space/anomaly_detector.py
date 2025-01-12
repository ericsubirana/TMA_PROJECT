#!/usr/bin/python3

import sys
import time
import ctypes
import threading
from socket import inet_ntoa
from bcc import BPF
import numpy as np
import pandas as pd
from joblib import load

# Load the trained model
model_file = "/home/subi/Desktop/TMA_PROJECT/AI_training/incremental_model.joblib"
clf = load(model_file)

def preprocess_flow_for_ai(flow_data):
    # Extract features 
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

    #FUTURE IMPLEMETNATION 
    column_names = [
        'Flow Packets/s',
        'Flow Bytes/s',
        'Total Fwd Packets',
        'Total Backward Packets',
        'Total Length of Fwd Packets',
        'Total Length of Bwd Packets',
        'Min Packet Length',
        'Max Packet Length',
        'Packet Length Variance',
        'Flow Duration',
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
    scaler = load("/home/subi/Desktop/TMA_PROJECT/AI_training/scaler.joblib")  # Assuming you saved your scaler during training
    features_scaled = scaler.transform(features_df)
    
    return features_scaled

def predict_flow_behavior(flow_data):
    # Preprocess the flow data for the model
    features = preprocess_flow_for_ai(flow_data)
    
    # Make a prediction
    prediction = clf.predict(features)
    
    # Return the prediction result
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
    with open("/home/subi/Desktop/TMA_PROJECT/kernel_space/packet_capture.c", "r") as f:
        c_code = f.read()

    c_code = f"""{c_code}"""
    b = BPF(text=c_code)
    fn_capture_packet = b.load_func("capture_packet", BPF.XDP)
    b.attach_xdp(dev="enp0s3", fn=fn_capture_packet, flags=0)

    def getting_unupdated_flows(threshold_seconds=20, active_timeout=60):
        flows_map = b.get_table("flows")
        exported_flows_map = b.get_table("exported_flows")
        current_time_ns = time.monotonic_ns()  # Use monotonic_ns to avoid desynchronization
        print(f"Processing flows with idle_timeout={threshold_seconds}s and active_timeout={active_timeout}s:")

        for key, per_cpu_data in flows_map.items():
            src_ip = inet_ntoa(ctypes.c_uint32(key.src_ip).value.to_bytes(4, 'big'))
            dst_ip = inet_ntoa(ctypes.c_uint32(key.dst_ip).value.to_bytes(4, 'big'))

            # Collect per-flow information from all CPUs
            last_seen = max(cpu_data.last_seen for cpu_data in per_cpu_data)
            first_seen = min(cpu_data.first_seen for cpu_data in per_cpu_data if cpu_data.first_seen > 0)

            # Validate that `first_seen` makes sense
            if first_seen == 0 or first_seen > current_time_ns:
                print(f"Warning: Invalid first_seen value for flow: src_ip={src_ip}, dst_ip={dst_ip}")
                continue

            # Calculate durations
            idle_duration = (current_time_ns - last_seen) / 1e9
            active_duration = (current_time_ns - first_seen) / 1e9

            # Check if the flow should be exported
            if idle_duration > threshold_seconds or active_duration > active_timeout:
                # Perform the summing operations only when the flow is exported
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

                print(f"Exporting flow: src_ip={src_ip}, dst_ip={dst_ip}, src_port={key.src_port}, "
                        f"dst_port={key.dst_port}, protocol={key.protocol}, "
                        f"packet_count={total_packets}, byte_count={total_byte_count}, "
                        f"fwd_packet_count={fwd_packet_count}, bwd_packet_count={bwd_packet_count}, "
                        f"fwd_byte_count={fwd_byte_count}, bwd_byte_count={bwd_byte_count}, "
                        f"min_packet_length={min_packet_length}, max_packet_length={max_packet_length}, "
                        f"packet_length_square_sum={packet_length_square_sum}, flow_duration={flow_duration:.2f}s, "
                        f"flow_iat_total={flow_iat_total}, flow_iat_min={flow_iat_min}, flow_iat_max={flow_iat_max}, "
                        f"fwd_iat_total={fwd_iat_total}, fwd_iat_min={fwd_iat_min}, fwd_iat_max={fwd_iat_max}, "
                        f"bwd_iat_total={bwd_iat_total}, bwd_iat_min={bwd_iat_min}, bwd_iat_max={bwd_iat_max}, "
                        f"syn_count={syn_count}, ack_count={ack_count}, psh_count={psh_count}, "
                        f"urg_count={urg_count}, fin_count={fin_count}, rst_count={rst_count}, "
                        f"idle_duration={idle_duration:.2f}s, active_duration={active_duration:.2f}s")

                # Export the flow and remove from the flows map
                new_data = FlowData(
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

                exported_flows_map[key] = new_data

                prediction = predict_flow_behavior(exported_flows_map[key])
                src_ip = inet_ntoa(ctypes.c_uint32(key.src_ip).value.to_bytes(4, 'big'))
                dst_ip = inet_ntoa(ctypes.c_uint32(key.dst_ip).value.to_bytes(4, 'big'))
                print(f"Flow from {src_ip} to {dst_ip} is: {prediction}")
                if prediction == "ANOMALY DETECTED":
                    print(f"ALERT: Anomalous flow detected from {src_ip} to {dst_ip}!")
                else:
                    print(f"Flow from {src_ip} to {dst_ip} is: {prediction}")
                del flows_map[key]  # Remove flow from map

    def periodic_print_flows(interval):
        def print_and_reschedule():
            getting_unupdated_flows()
            threading.Timer(interval, print_and_reschedule).start()

        print_and_reschedule()

    # Start the periodic function
    periodic_print_flows(3)

except KeyboardInterrupt:
    b.remove_xdp(dev="enp0s3", flags=0)
    sys.exit()