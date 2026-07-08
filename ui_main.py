#!/usr/bin/env python3
"""
AI Assistant Desktop Frontend - Main Application
Production-quality PySide6 interface for voice assistant

Architecture:
- MainWindow: Top-level orchestrator
- LeftPanel: Brain visualization area (70% width)
- RightPanel: Camera feed + Conversation (30% width)
- Threading: All heavy operations in worker threads
- Signals/Slots: Safe inter-thread communication
"""

import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QHBoxLayout, QFrame
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon

from ui_components.left_panel import LeftPanel
from ui_components.right_panel import RightPanel
from ui_components.styles import setup_dark_theme


class MainWindow(QMainWindow):
    """
    Main application window - orchestrates left and right panels
    Handles window configuration, layout, and theme setup
    """
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JARVIS - AI Assistant")
        self.setMinimumSize(1400, 800)
        self.resize(1600, 900)
        
        # Setup theme
        setup_dark_theme(self)
        
        # Create main widget and layout
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create panels
        self.left_panel = LeftPanel()
        self.right_panel = RightPanel()
        panel_divider = QFrame()
        panel_divider.setFixedWidth(1)
        panel_divider.setStyleSheet("QFrame { background-color: #58e7ff; border: none; }")
        
        # Add to layout with 70/30 split
        main_layout.addWidget(self.left_panel, 7)
        main_layout.addWidget(panel_divider, 0)
        main_layout.addWidget(self.right_panel, 3)
        
        # Set central widget
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        
        # Set window icon (if available)
        try:
            self.setWindowIcon(QIcon("assets/jarvis_icon.png"))
        except:
            pass
        
        # Center window on screen
        self._center_window()
    
    def _center_window(self):
        """Center window on screen"""
        screen = self.screen()
        if screen:
            center_point = screen.geometry().center()
            self.move(center_point.x() - self.width() // 2, 
                     center_point.y() - self.height() // 2)
    
    def closeEvent(self, event):
        """Cleanup when closing"""
        self.left_panel.cleanup()
        self.right_panel.cleanup()
        event.accept()


def main():
    """Application entry point"""
    app = QApplication(sys.argv)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
