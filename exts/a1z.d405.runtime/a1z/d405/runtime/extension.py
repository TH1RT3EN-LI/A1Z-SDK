import carb
import omni.ext


class Extension(omni.ext.IExt):
    def on_startup(self, ext_id: str):
        carb.log_info(f"A1Z D405 runtime extension started: {ext_id}")

    def on_shutdown(self):
        carb.log_info("A1Z D405 runtime extension stopped.")
