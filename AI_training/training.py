import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.preprocessing import LabelEncoder, StandardScaler
from joblib import dump, load
import os

# Path to the model file
model_file = "incremental_model.joblib"
scaler_file = "scaler.joblib"
# Load the CSV file
def load_dataset(csv_file):
    # Load dataset
    df = pd.read_csv(csv_file, header=None)

    column_names = [
        "Destination Port", "Flow Duration", "Total Fwd Packets", "Total Backward Packets",
        "Total Length of Fwd Packets", "Total Length of Bwd Packets", "Fwd Packet Length Max",
        "Fwd Packet Length Min", "Fwd Packet Length Mean", "Fwd Packet Length Std",
        "Bwd Packet Length Max", "Bwd Packet Length Min", "Bwd Packet Length Mean", "Bwd Packet Length Std",
        "Flow Bytes/s", "Flow Packets/s", "Flow IAT Mean", "Flow IAT Std", "Flow IAT Max", "Flow IAT Min",
        "Fwd IAT Total", "Fwd IAT Mean", "Fwd IAT Std", "Fwd IAT Max", "Fwd IAT Min",
        "Bwd IAT Total", "Bwd IAT Mean", "Bwd IAT Std", "Bwd IAT Max", "Bwd IAT Min",
        "Fwd PSH Flags", "Bwd PSH Flags", "Fwd URG Flags", "Bwd URG Flags", "Fwd Header Length",
        "Bwd Header Length", "Fwd Packets/s", "Bwd Packets/s", "Min Packet Length", "Max Packet Length",
        "Packet Length Mean", "Packet Length Std", "Packet Length Variance", "FIN Flag Count",
        "SYN Flag Count", "RST Flag Count", "PSH Flag Count", "ACK Flag Count", "URG Flag Count",
        "CWE Flag Count", "ECE Flag Count", "Down/Up Ratio", "Average Packet Size", "Avg Fwd Segment Size",
        "Avg Bwd Segment Size", "Fwd Header Length", "Fwd Avg Bytes/Bulk", "Fwd Avg Packets/Bulk",
        "Fwd Avg Bulk Rate", "Bwd Avg Bytes/Bulk", "Bwd Avg Packets/Bulk", "Bwd Avg Bulk Rate",
        "Subflow Fwd Packets", "Subflow Fwd Bytes", "Subflow Bwd Packets", "Subflow Bwd Bytes",
        "Init_Win_bytes_forward", "Init_Win_bytes_backward", "act_data_pkt_fwd", "min_seg_size_forward",
        "Active Mean", "Active Std", "Active Max", "Active Min", "Idle Mean", "Idle Std", "Idle Max",
        "Idle Min", "Label"
    ]

    df.columns = column_names

    # Handle missing values
    df.fillna(0, inplace=True)

    # Select only the relevant columns for your task
    selected_columns = [
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
        "Label"
    ]
    df = df[selected_columns]

    return df

# Preprocess the dataset
def preprocess_data(df, scaler=None):
    # Separate features and labels
    y = df["Label"].apply(lambda x: 1 if x == "BENIGN" else 0).to_numpy() #1 GOOD | 0 BAD
    X = df.drop(columns=["Label"])

    # Encode categorical features
    categorical_columns = X.select_dtypes(include=["object"]).columns
    label_encoders = {}
    for col in categorical_columns:
        le = LabelEncoder()
        X[col] = le.fit_transform(X[col].astype(str))
        label_encoders[col] = le

    # Normalize the features
    if scaler is None:
        scaler = StandardScaler()
        X = scaler.fit_transform(X)
    else:
        X = scaler.transform(X)

    return X, y, scaler, label_encoders

# Load or initialize the model
def load_or_initialize_model(input_dim):
    if os.path.exists(model_file):
        print("Loading existing model...")
        model = load(model_file)
    else:
        print("No existing model found. Training a new one...")
        model = SGDClassifier(loss="log_loss", random_state=42)  # Use 'log' for logistic regression
    return model

def load_or_initialize_scaler():
    if os.path.exists(scaler_file):
        print("Loading existing scaler...")
        scaler = load(scaler_file)
    else:
        print("No existing scaler found. Creating a new one...")
        scaler = None
    return scaler

# Main training and saving logic
def train_and_save_model(csv_file):
    # Load and preprocess the data
    df = load_dataset(csv_file)

    # Load or initialize the scaler
    scaler = load_or_initialize_scaler()
    X, y, scaler, label_encoders = preprocess_data(df, scaler)

    # Save the scaler
    if scaler and not os.path.exists(scaler_file):
        dump(scaler, scaler_file)
        print(f"Scaler saved to {scaler_file}")

    # Load or initialize the model
    clf = load_or_initialize_model(X.shape[1])

    # Incrementally train the model
    print("Incrementally training the model...")
    clf.partial_fit(X, y, classes=[0, 1])

    # Save the model
    dump(clf, model_file)
    print(f"Model saved to {model_file}")

    # Evaluate the model
    y_pred = clf.predict(X)
    accuracy = accuracy_score(y, y_pred)
    print(f"Accuracy: {accuracy:.4f}")
    print("Classification Report:")
    print(classification_report(y, y_pred))

# Example usage
if __name__ == "__main__":
    file_names = {
        "Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv",
        "Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv",
        "Friday-WorkingHours-Morning.pcap_ISCX.csv",
        "Monday-WorkingHours.pcap_ISCX.csv",
        "Thursday-WorkingHours-Afternoon-Infilteration.pcap_ISCX.csv",
        "Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv",
        "Tuesday-WorkingHours.pcap_ISCX.csv",
        "Wednesday-workingHours.pcap_ISCX.csv",
    }

    for csv_file in file_names:
        file_path = f"archive/{csv_file}"
        train_and_save_model(file_path)
