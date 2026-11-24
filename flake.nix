{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs {
          inherit system;
        };
      in
      {
        devShells.default = pkgs.mkShell {
          packages = with pkgs; [
            (swim.overrideAttrs (
              finalAttrs: previousAttrs: {
                src = pkgs.fetchFromCodeberg {
                  owner = "ChocolateLoverRaj";
                  repo = "swim";
                  rev = "gowin-pack-err";
                  hash = "sha256-x558dv1Xfd9MtkPbnaaN7NmRi847468o5uPO6PJVQAw=";
                };
                cargoHash = "sha256-IxEdK1bnoFXZYnTxmGI71h0WyrZ+Bu7twkUVLO7mIUo=";
              }
            ))
            (surfer.overrideAttrs (
              finalAttrs: previousAttrs: {
                src = pkgs.fetchFromGitLab {
                  owner = "surfer-project";
                  repo = "surfer";
                  rev = "c2d17a6457bba6204143f3c6f7fd3c58cf893837";
                  hash = "sha256-Hf9nDK/6taP8AFXDOzVwpl7WlBxG6pjyaqUOA2te2nQ=";
                };
                cargoHash = "sha256-6dOoPMxOW2+vlTPXQME7OMeXLfWGyi7H3PY77x22TWY=";
              }
            ))
            uv
            iverilog
          ];
        };
      }
    );
}
