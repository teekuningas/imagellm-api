.PHONY: shell
shell:
	nix develop

.PHONY: watch
watch:
	uvicorn main:app --reload

.PHONY: build
build:
	nix build .#dockerImage
	podman load -i result

.PHONY: nix-%
nix-%:
	nix develop \
		--command $(MAKE) $*

FORCE:
