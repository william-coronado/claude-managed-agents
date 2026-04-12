# Plan
## Goal
I want to create a scaffolding project in Python using Claude Managed Agents to be able to implement a number of use cases. Some examples: 
- Software Engineering: a team of agents for planning/solution architecture, coding, code reviewing, testing, etc.
- Content creator: web research, authoring, publishing, etc.

## Starting ideas
The following are the starting requirements. Please suggest alternatives if a better practice is more suitable. Also, do not hesitate to modify or add to this in order to have a complete working prototype:
- Use Claude API Docs as reference for entities, definitions and parameters: https://platform.claude.com/docs/en/managed-agents/
- Environment config file: a list of environments to create when setting up the workspace for first time, each one with: name (compulsory), description, and config (with params: networking, and packages).
- Agents config file: a list of agents to create when setting up the workspace for first time, each one with: name (compulsory), model, description, mcp servers, skills.
- Global config file with: ANTHROPIC_API_KEY, default Claude model (used when no model is provided to an agent), path to environment config file, and path to agents config file.
- Environment python module: create an instance of an environment class with params as per config file, and an additional boolean parameter "existing" (default value: False) that if True then it will try to find an existing environment with same name and return an environment object.
- Agent python module: create an instance of an agent class with params as per config file, and an additional boolean parameter to use existing agent (default value: False) that if True then it will try to find an existing agent with same name and return an agent object.
- Session python module: create a new session with parameters as per Platform API documentation. It returns a session object.
- A python module to send messages and handle response stream
- A python script to orchestrate all above modules, it reads the config files and if ANTHROPIC_API_KEY exists as environment variable uses it, otherwise reads it from the global config file and raises an error if not present in either. This script will send prompt messages.
- Suggest a folder structure where to put every single piece (e.g. config, src, utils, use_cases, etc.).

## Use Cases
- Each use case comprises agents with tools fit for purpose.
- Maybe an environment for each use case?
- Maybe a workspace for each use case?
- The initial version should contain a template for the two use cases mentioned in the Goal section.