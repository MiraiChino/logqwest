from pathlib import Path
from src.utils.config import ConfigManager
from src.utils.file_handler import FileHandler
from src.utils.progress import ProgressTracker
from src.ui.controller import UIController

def main():
    config = ConfigManager(Path("prompt/config.json"))
    file_handler = FileHandler(config.paths)
    progress_tracker = ProgressTracker(file_handler)
    
    controller = UIController(file_handler, progress_tracker)
    controller.run()

if __name__ == "__main__":
    main()
