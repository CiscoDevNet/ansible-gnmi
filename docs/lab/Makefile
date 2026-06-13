# Convenience targets for the Cisco gNMI / gNOI lab.
#
# The playbooks run with the SYSTEM ansible-playbook (its Python deps for the
# device modules come from ./venv via ansible_python_interpreter in the
# inventory). Linting uses an isolated ./.lintenv so it never disturbs the
# run environment.

PLAYBOOKS := playbooks
LINTENV   := .lintenv
LIMIT     ?=
EXTRA     ?=

# Turn LIMIT/EXTRA into ansible-playbook flags when provided.
LIMIT_FLAG := $(if $(LIMIT),--limit $(LIMIT),)
EXTRA_FLAG := $(if $(EXTRA),-e "$(EXTRA)",)
AP = ansible-playbook $(LIMIT_FLAG) $(EXTRA_FLAG)

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

# --- Setup ----------------------------------------------------------------
.PHONY: setup
setup: ## Create venv + install Python and collection deps
	python3 -m venv venv
	./venv/bin/pip install -r requirements.txt
	ansible-galaxy collection install -r requirements.yml

# --- Read-only / safe -----------------------------------------------------
.PHONY: caps
caps: ## gNMI Capabilities (and write models/<host>_models.txt)
	$(AP) $(PLAYBOOKS)/00_capabilities.yml

.PHONY: get
get: ## gNMI GET
	$(AP) $(PLAYBOOKS)/01_get.yml

.PHONY: subscribe
subscribe: ## gNMI Subscribe (once / stream / on_change)
	$(AP) $(PLAYBOOKS)/03_subscribe.yml

.PHONY: smoke
smoke: ## Safe end-to-end check: capabilities -> GET -> Subscribe
	$(AP) $(PLAYBOOKS)/00_capabilities.yml
	$(AP) $(PLAYBOOKS)/01_get.yml
	$(AP) $(PLAYBOOKS)/03_subscribe.yml

# --- Mutating (still reversible) ------------------------------------------
.PHONY: set-check
set-check: ## gNMI SET dry-run (--check --diff, no changes)
	$(AP) $(PLAYBOOKS)/02_set.yml --check --diff

.PHONY: set
set: ## gNMI SET (applies then restores the demo change)
	$(AP) $(PLAYBOOKS)/02_set.yml --diff

.PHONY: cert
cert: ## gNOI certificate management (read-only ops)
	$(AP) $(PLAYBOOKS)/04_gnoi_cert.yml

# --- Quality --------------------------------------------------------------
.PHONY: lint
lint: $(LINTENV) ## Run yamllint + ansible-lint in the isolated lint env
	./$(LINTENV)/bin/yamllint .
	./$(LINTENV)/bin/ansible-lint $(PLAYBOOKS)

.PHONY: syntax
syntax: ## ansible-playbook --syntax-check on every playbook
	@for pb in $(PLAYBOOKS)/*.yml; do \
		printf '%-40s ' "$$pb"; \
		ansible-playbook --syntax-check "$$pb" >/dev/null && echo OK || echo FAIL; \
	done

$(LINTENV):
	python3 -m venv $(LINTENV)
	./$(LINTENV)/bin/pip install -q yamllint ansible-lint

.PHONY: clean
clean: ## Remove generated artifacts (backups, model lists)
	rm -f backups/*.json models/*.txt
