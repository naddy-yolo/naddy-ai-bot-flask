# utils/env_utils.py

def update_env_variable(file_path: str, key: str, new_value: str):
    lines = []
    key_found = False

    with open(file_path, "r") as f:
        for line in f:
            if line.startswith(f"{key}="):
                lines.append(f"{key}={new_value}\n")
                key_found = True
            else:
                lines.append(line)

    if not key_found:
        lines.append(f"{key}={new_value}\n")

    with open(file_path, "w") as f:
        f.writelines(lines)
