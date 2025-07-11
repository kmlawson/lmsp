# Project: lmsp CLI

## Project Overview
- Goal of this app is to build a simple CLI called lmsp which, when run, will send a prompt to a local lm-studio loaded model (default the first loaded model returned by "lms ps") and return to the shell the response of the model.
- Models must be pre-loaded using "lms load <model>" or LM Studio desktop app - lmsp will not auto-load models. 

## Planned Features
- Eventually we would like to add these features:
  - Ability to pipe text documents to include after the main prompt argument
  - Ability to attach images with -a for models that support image input
  - Ability to continue from last prompt

## Development Guidelines
- When adding new features, always add a test first for it, then implement the feature and test it
- Put all tests in the tests directory