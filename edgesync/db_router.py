class DatabaseRouter:
    """
    A router to control all database operations on models
    """
    
    mosquitto_models = {
        'mosquittouser', 'mosquittoacl', 'mosquittosuperuser'
    }
    
    def db_for_read(self, model, **hints):
        """Suggest the database to read from."""
        if (model._meta.app_label in ['sensors', 'user'] and 
            model.__name__.lower() in self.mosquitto_models):
            return 'mosquitto'
        return 'default'
    
    def db_for_write(self, model, **hints):
        """Suggest the database to write to."""
        if (model._meta.app_label in ['sensors', 'user'] and 
            model.__name__.lower() in self.mosquitto_models):
            return 'mosquitto'
        return 'default'
    
    def allow_relation(self, obj1, obj2, **hints):
        """Allow relations if models are in the same app."""
        db_set = {'default', 'mosquitto'}
        if obj1._state.db in db_set and obj2._state.db in db_set:
            return True
        return None
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Ensure that certain models get created on the right database."""
        if app_label in ['sensors', 'user']:
            if model_name and model_name.lower() in self.mosquitto_models:
                return db == 'mosquitto'
            elif app_label == 'sensors' and model_name and model_name.lower() == 'sensordata':
                return db == 'default'
            elif app_label == 'sensors' and model_name and model_name.lower() == 'device':
                return db == 'default'
            elif app_label == 'user':
                return db == 'default'
        if db == 'mosquitto':
            return (app_label in ['sensors', 'user'] and 
                    model_name and model_name.lower() in self.mosquitto_models)
        return db == 'default'