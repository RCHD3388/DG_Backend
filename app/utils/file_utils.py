import shutil
from pathlib import Path
from app.utils.CustomLogger import CustomLogger

logger = CustomLogger("FileUtils")


def clear_directory_contents(dir_path: Path) -> int:
    # Step 1: Validate that the path exists and is a directory.
    # If not, do nothing as requested.
    if not dir_path.is_dir():
        logger.warning_print(f"Directory '{dir_path}' not found. No action taken.")
        return 0

    logger.info_print(f"Clearing contents of directory: '{dir_path}'...")
    deleted_items_count = 0

    # Step 2: Iterate over all items in the directory and delete them.
    for item in dir_path.iterdir():
        try:
            if item.is_file() or item.is_symlink():
                # Use .unlink() to delete files or symbolic links.
                item.unlink()
                deleted_items_count += 1
            elif item.is_dir():
                # Use shutil.rmtree() to recursively delete directories and their contents.
                shutil.rmtree(item)
                deleted_items_count += 1
        except Exception as e:
            # Log an error if a specific item fails to be deleted, but allow the process to continue.
            logger.error_print(f"Failed to delete {item}: {e}")
            # If any failure should stop the entire process, you can uncomment the next line:
            # raise

    logger.info_print(f"Successfully cleared directory '{dir_path}'. Total items deleted: {deleted_items_count}.")
    
    # Step 3: Return the total count of deleted items.
    return deleted_items_count
