#!/bin/bash

# Function to check if a command exists
command_exists() {
  command -v "$1" >/dev/null 2>&1
}

# Install pv if it is not installed
install_dependencies() {
  if ! command_exists brew; then
    echo "Homebrew is not installed. Please install Homebrew first."
    exit 1
  fi

  if ! command_exists pv; then
    echo "Installing pv..."
    brew install pv
  fi
}

# Check and install dependencies
install_dependencies

# Define the files and commands
files=("Bin/Default/loading1.bin" "Bin/Default/loading2.bin" "eink_driver_sam.py" "main.py")
port="/dev/tty.usb*"

# Total number of files
total_files=${#files[@]}

# Function to display loading bar
display_loading_bar() {
  progress=$(($1 * 100 / $total_files))
  bar=$(printf "%-${progress}s" "#" | tr ' ' '#')
  echo -ne "Progress: [${bar}] ${progress}%\r"
}

# Iterate over each file and upload with progress bar
for ((i = 0; i < total_files; i++)); do
  file=${files[$i]}
  echo "Uploading $file"
  ampy --port $port put $file
  display_loading_bar $((i + 1))
done

# Move to a new line after the progress bar
echo -e "\nAll files uploaded successfully."
