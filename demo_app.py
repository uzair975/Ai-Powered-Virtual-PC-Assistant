#!/usr/bin/env python3
"""
Demo Application - Testing and Mock Data
Shows how to integrate UI with backend and test components
"""

import sys
from PySide6.QtCore import QTimer, Signal, QObject
from ui_main import MainWindow
from PySide6.QtWidgets import QApplication
from ui_components.backend_connector import BackendConnector


class MockBackend(QObject):
    """Mock backend for testing without voice assistant"""
    
    def __init__(self):
        super().__init__()
    
    @staticmethod
    def get_sample_responses():
        """Sample assistant responses"""
        return [
            ("What is the weather today?", "The weather is clear with a high of 72Â°F."),
            ("Open Google", "Opening Google in default browser..."),
            ("Increase brightness", "Brightness increased to 75%."),
            ("Play music", "Now playing your favorite playlist."),
            ("What time is it?", "The current time is 3:45 PM."),
            ("Set a reminder", "Reminder set for 5:00 PM."),
            ("Tell me a joke", "Why did the AI go to school? Because it wanted to improve its learning model!"),
        ]


class DemoApplication(MainWindow):
    """Extended MainWindow for demo with mock interactions"""
    
    def __init__(self):
        super().__init__()
        
        # Setup backend connector (without real engines for demo)
        self.backend = BackendConnector()
        self.backend.command_recognized.connect(self._on_command)
        self.backend.assistant_response.connect(self._on_response)
        self.backend.system_status.connect(self._on_status)
        
        # Demo timer
        self.demo_timer = QTimer()
        self.demo_timer.timeout.connect(self._demo_step)
        
        # Demo state
        self.demo_step = 0
        self.mock_backend = MockBackend()
        
        # Start demo after 2 seconds
        QTimer.singleShot(2000, self._start_demo)
    
    def _start_demo(self):
        """Start demo sequence"""
        print("[DEMO] Starting demo sequence...")
        self.right_panel.add_system_message("Demo mode activated. Running sample commands...")
        self.demo_timer.start(3000)  # Every 3 seconds
    
    def _demo_step(self):
        """Execute one demo step"""
        responses = self.mock_backend.get_sample_responses()
        
        if self.demo_step < len(responses):
            command, response = responses[self.demo_step]
            
            # Simulate user command
            print(f"[DEMO] Simulating: {command}")
            self.right_panel.add_user_command(command)
            self.left_panel.add_history_entry(command, response)
            
            # Simulate assistant response (with typing animation)
            QTimer.singleShot(500, lambda: self.right_panel.add_assistant_response(response, animate=True))
            
            self.demo_step += 1
        else:
            # Demo finished
            self.demo_timer.stop()
            self.right_panel.add_system_message("Demo sequence complete. Ready for voice input.")
    
    def _on_command(self, command: str, confidence: float):
        """Handle command recognized"""
        print(f"[BACKEND] Command: {command} ({confidence:.2f})")
    
    def _on_response(self, response: str):
        """Handle response"""
        print(f"[BACKEND] Response: {response}")
    
    def _on_status(self, status: str, message: str):
        """Handle status update"""
        print(f"[BACKEND] Status: {status} - {message}")
    
    def closeEvent(self, event):
        """Cleanup on close"""
        self.demo_timer.stop()
        self.backend.cleanup()
        super().closeEvent(event)


def run_demo():
    """Run demo application"""
    app = QApplication(sys.argv)
    
    window = DemoApplication()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    print("=" * 60)
    print("JARVIS - AI Assistant Frontend (Demo Mode)")
    print("=" * 60)
    print("\nFeatures demonstrated:")
    print("  âœ“ Brain animation (left panel)")
    print("  âœ“ Camera feed (top right)")
    print("  âœ“ Conversation with typing animation (bottom right)")
    print("  âœ“ Command history (click clock icon)")
    print("  âœ“ Dark theme with orange accents")
    print("  âœ“ Responsive layout (70/30 split)")
    print("\nStarting demo in 2 seconds...\n")
    
    run_demo()

