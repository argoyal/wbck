# Introduction
The intention of this project is that setting up workspaces is a difficult task when
someone has to change / format present system.
Running all the commands again, cloning all the projects again, backing up your documents
it is a nightmare.

This is a simple application for easy backup and restoration of project workspaces.
There is not much you can do with the app right now but yet it is powerful enough to save your workspaces.
The structure of a sample workspace I prefer can be found in the structure directory. The current cloud where the
backup goes is AWS. Hope to see collaborators to add more sources - Gdrive, Azure etc.


# Setup and Installation
- Clone the repository
- Install packages from `requirements.txt`

You are good to go.

# Configuration
A template configuration is available in `config_template.json`.
You need to configure the repository urls that you want to keep a track of.
The project is configured to have any folder-names for eg. `ml-apps`, `web-apps` etc.
Since each of these kinds of application can be subdivided under `client` and `internal`.
Again all of this is still configurable.

Once your configuration file is created you have to keep it under the folder - `configs`
You can keep a backup of these config files and reuse it when you want to restore this to a different system.

# Environment Variables
The application expects only 3 environment variables.
- `BUCKET_NAME`
- `AWS_KEY`
- `AWS_SECRET`

# Usage
- Entrypoint of the project is `run.py`
- The application provides 3 options:
    - setup: downloads a specific project details as specified in the config file
    - sync: creates a backup of data as specified in the config file
    - add: creates a copy of the project by `name` as specified in config in the `target_path` again as specified in the config
- Running a command is easy `python run.py <argument> <argument-value>`

# Contribution
This is a personal open project and still might need a lot of work to solve all the cases.
The current project serves my purpose. Feel free to raise PRs and add more features as per your choice.
