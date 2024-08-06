import json

class ConfigManager:
    def __init__(self, config_file="config.json"):
        self.config_file = config_file
        self.config = self.load_config()

    def load_config(self):
        try:
            with open(self.config_file, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return {"models": []}

    def save_config(self):
        with open(self.config_file, "w") as f:
            json.dump(self.config, f, indent=2)

    def add_model(self, model_config):
        self.config["models"].append(model_config)
        self.save_config()

    def remove_model(self, model_name):
        self.config["models"] = [m for m in self.config["models"] if m["name"] != model_name]
        self.save_config()

    def get_models(self):
        return self.config["models"]