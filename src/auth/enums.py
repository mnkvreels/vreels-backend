from enum import Enum

# Enum to represent different genders
class GenderEnum(str, Enum):
    MALE = "male"
    FEMALE = "female"

# Enum to hold the email pattern
class EmailPattern(Enum):
    EMAIL_REGEX = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    
# Enum to store the regex pattern for password validation
class PasswordPattern(Enum):
    PASSWORD_REGEX = r"^(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*(),.?\":{}|<>])[A-Za-z\d!@#$%^&*(),.?\":{}|<>]{8,12}$"
