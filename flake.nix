{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/23.05";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        pythonEnv = pkgs.python3.withPackages (ps: with ps; [
          fastapi
          uvicorn
        ]);
      in
      {
        devShell = pkgs.mkShell {
          buildInputs = [ pythonEnv ];
        };

        packages = {
          dockerImage = pkgs.dockerTools.buildImage {
            name = "imagellm-api";
            tag = "latest";
            runAsRoot = ''
              cp -r ${./.} /code
              chmod -R +w /code
            '';
            config = {
              Cmd = [ "uvicorn" "main:app" "--host" "0.0.0.0" "--port" "8001" ];
              WorkingDir = "/code";
            };
            copyToRoot = with pkgs; [ pythonEnv bashInteractive curl coreutils ];
          };
        };
      }
    );
}
