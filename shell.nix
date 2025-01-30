# shell.nix
{ pkgs ? import <nixpkgs> { } }: with pkgs;
let
  my-stdenv = pkgs.stdenv;
  pythonPackages = python312Packages;

in pkgs.mkShell.override {
  stdenv = my-stdenv;
} rec {
  name = "pop-fe2";
  venvDir = "./.venv";

  buildInputs = [

    pythonPackages.python
    pythonPackages.venvShellHook

    pythonPackages.requests
    pythonPackages.pycdio
    pythonPackages.distutils

    libsndfile git ffmpeg cmake
  ];

  # Now we can execute any commands within the virtual environment.
  postShellHook = ''
    export LD_LIBRARY_PATH="${pkgs.stdenv.cc.cc}/lib:$LD_LIBRARY_PATH"

    export LD_LIBRARY_PATH="${pkgs.lib.makeLibraryPath buildInputs}:$LD_LIBRARY_PATH"

    # Run pip.
    TMPDIR=/tmp pip install -r requirements.txt
  '';

}
