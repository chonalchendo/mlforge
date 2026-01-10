"""Entity definitions for recommendation system."""

import mlforge as mlf

user = mlf.Entity(name="user", join_key="user_id")
item = mlf.Entity(name="item", join_key="item_id")
