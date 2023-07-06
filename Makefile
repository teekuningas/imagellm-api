.PHONY: shell
shell:
	nix develop

.PHONY: watch
watch:
	IMAGELLM_DEV=true uvicorn main:app --reload

.PHONY: format
format:
	black main.py

.PHONY: build
build:
	nix build .#dockerImage
	podman load -i result

.PHONY: nix-%
nix-%:
	nix develop \
		--command $(MAKE) $*

FORCE:
