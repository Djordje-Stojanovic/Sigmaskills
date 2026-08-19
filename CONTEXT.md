# SigmaSkills

SigmaSkills distributes a small, portable set of Agent Skills across compatible coding-agent hosts.

## Language

**Skill Pack**:
The four installable SigmaSkills published together from this repository.
_Avoid_: Bundle, plugin

**Sigma Installer**:
A Sigma-branded interactive installer that lets a person select skills from the Skill Pack.
_Avoid_: Matt's installer, generic installer

**Agent Host**:
A coding-agent product that can receive and load installed Agent Skills.
_Avoid_: Agent, platform

**Project Installation**:
A Skill Pack installation owned by one project. This is the preferred installation scope.
_Avoid_: Local installation

**Global Installation**:
A Skill Pack installation available to projects for one operating-system user.
_Avoid_: Public installation, machine installation

**Skill Customization**:
Additive user-authored instructions attached to one installed skill and preserved when its upstream content updates. It cannot replace or delete official instructions.
_Avoid_: Fork, arbitrary patch, manual edit

**Release**:
A named, public version of the complete Skill Pack.
_Avoid_: Skill version

**Skill Revision**:
The content identity of one skill within a Release, represented by a deterministic hash.
_Avoid_: Release, per-skill version

**Uninstall Review**:
A required per-skill decision during uninstall, including for unchanged skills. Changed or customized skills offer preservation choices before removal.
_Avoid_: Batch uninstall
