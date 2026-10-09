import subprocess
import time
import sys
import os

class SystemLauncher:
    def __init__(self):
        self.base_path = os.path.dirname(os.path.abspath(__file__))

    def launch(self):
        print("--- AUTOMOTIVE DIAGNOSTIC SYSTEM (OOP) ---")
        
        # 1. Khởi chạy PC2 (Receiver) trong cửa sổ CMD riêng
        print("Starting Receiver Module...")
        pc2_path = os.path.join(self.base_path, "pc2_receiver.py")
        subprocess.Popen(["start", "cmd", "/k", sys.executable, pc2_path], shell=True)
        
        time.sleep(1.5) # Chờ cổng 5005 sẵn sàng

        # 2. Khởi chạy PC1 (UI Master)
        print("Starting Simulator UI...")
        pc1_path = os.path.join(self.base_path, "pc1_simulator.py")
        subprocess.run([sys.executable, pc1_path])

if __name__ == "__main__":
    launcher = SystemLauncher()
    launcher.launch()