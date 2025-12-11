"""
Demo script - Khởi tạo nhiều instance
"""
import subprocess
import sys
import time
import os

def main():
    instances = [
        {"name": "Alice", "port": 5000},
        {"name": "Bob", "port": 5001},
        {"name": "Charlie", "port": 5002},
        {"name": "Diana", "port": 5003},
    ]
    
    processes = []
    script_dir = os.path.dirname(os.path.abspath(__file__))
    main_script = os.path.join(script_dir, "main.py")
    
    print("=" * 50)
    print("🚀 LAN CHAT DEMO")
    print("=" * 50)
    
    for i, inst in enumerate(instances):
        cmd = [sys.executable, main_script, "-n", inst["name"], "-p", str(inst["port"])]
        print(f"  → Khởi động {inst['name']} (port {inst['port']})")
        
        proc = subprocess.Popen(cmd, cwd=script_dir)
        processes.append(proc)
        
        # Delay 2 giây giữa các instance
        if i < len(instances) - 1:
            print("    Đợi 2 giây...")
            time.sleep(2)
    
    print()
    print("=" * 50)
    print("✅ Đã khởi động tất cả!")
    print("💡 Ctrl+C để dừng")
    print("=" * 50)
    
    try:
        for proc in processes:
            proc.wait()
    except KeyboardInterrupt:
        print("\n⏹️ Đang dừng...")
        for proc in processes:
            proc.terminate()

if __name__ == "__main__":
    main()