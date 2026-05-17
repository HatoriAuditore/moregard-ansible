# Ansible Configuration Repository

This repository contains the Ansible layer used after Terraform has created or changed virtual machines.

## Repository purpose

The repository is designed to be triggered from GitLab CI either:

- as a downstream step after Terraform apply
- or as a standalone Ansible-only run through the backend API

It provides:

- a mandatory Linux bootstrap playbook
- optional service profiles
- a dedicated Tomcat installation playbook
- CI logic for syntax check and configuration runs

## Repository structure

- `.gitlab-ci.yml`  
  GitLab CI pipeline for validation and configuration.
- `ansible.cfg`  
  Ansible defaults and inventory path.
- `inventory/hosts.ini`  
  Inventory file. Replace placeholder values with environment-specific hosts.
- `inventory/group_vars/all.yml`  
  Shared variables used by the playbooks and roles.
- `playbooks/bootstrap_linux.yml`  
  Mandatory baseline configuration for Linux VMs.
- `playbooks/site.yml`  
  Optional service configuration playbook.
- `playbooks/tomcat.yml`  
  Dedicated Apache Tomcat installation playbook.
- `roles/`  
  Reusable roles for baseline and service setup.

## Playbooks

### `playbooks/bootstrap_linux.yml`

Used for mandatory first-pass configuration of a VM. It currently covers:

- proxy configuration
- hostname / FQDN
- timezone
- NTP
- bootstrap users
- root CA installation
- Zabbix agent installation and configuration
- audit marker files

### `playbooks/site.yml`

Used for optional service profiles. The playbook applies roles only when the requested service profile is present.

Current service roles:

- `nginx`
- `ftp_server`
- `tomcat`

The `ftp` service profile used by the CLI maps to the `ftp_server` role in this repository.

The `tomcat` service profile installs Apache Tomcat 10.1.x together with Eclipse Temurin OpenJDK 21.

### `playbooks/tomcat.yml`

Used for direct installation of Apache Tomcat without relying on the service-profile flow in `site.yml`.

## Roles

- `proxy_client`
- `common_base`
- `root_ca`
- `zabbix_agent`
- `nginx`
- `ftp_server`
- `tomcat`

## CI behavior

The GitLab pipeline contains two stages:

1. `validate`  
   Installs Ansible and runs syntax check.
2. `configure`  
   Runs the selected playbook against the selected inventory target.

The pipeline accepts API-triggered runs as well as downstream pipeline triggers.

Important variables used by CI:

- `ANSIBLE_INVENTORY_FILE`
- `ANSIBLE_PLAYBOOK`
- `ANSIBLE_LIMIT`
- `ANSIBLE_EXTRA_VARS_JSON`
- `VM_REQUEST_ID`
- `VM_REQUESTED_BY`
- `VM_OPERATION`
- `VM_NAMES`
- `VM_NAMES_JSON`

## Environment-specific data

This repository should not store production secrets.

Before using it in a real environment, review and customize:

- `inventory/hosts.ini`
- `inventory/group_vars/all.yml`
- any internal proxy, NTP, certificate, or monitoring settings
- Tomcat and Java role defaults such as the Temurin repository distribution, Tomcat version, and Java home path

## Notes

- Keep real inventory values outside public source control when possible.
- If the repository is used in more than one environment, prefer templating or local overrides instead of hard-coding environment-specific values.
