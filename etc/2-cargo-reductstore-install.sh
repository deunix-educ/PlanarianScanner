!/bin/bash
echo "--- install reductstore"

sudo apt install libprotobuf-dev protobuf-compiler

curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

source $HOME/.cargo/env
cargo --version
rustc --version
cargo install reductstore

