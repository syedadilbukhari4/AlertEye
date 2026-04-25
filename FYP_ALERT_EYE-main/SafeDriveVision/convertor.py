import os

root = "yolov5"
for subdir, _, files in os.walk(root):
    for f in files:
        if f.endswith(".py"):
            path = os.path.join(subdir, f)
            with open(path, "r") as file:
                content = file.read()
            new_content = content.replace("from utils", "from utils")
            if new_content != content:
                with open(path, "w") as file:
                    file.write(new_content)
                print(f"Fixed imports in {path}")
