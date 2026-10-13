from django.core.validators import RegexValidator

# Pakistani CNIC / NIC, stored in the dashed NADRA layout
cnic_validator = RegexValidator(r'^\d{5}-\d{7}-\d$', 'Enter a CNIC as 12345-1234567-1 (13 digits).')
mobile_validator = RegexValidator(r'^(03\d{9}|\+923\d{9})$', 'Enter a mobile number as 03XXXXXXXXX or +923XXXXXXXXX.')
landline_validator = RegexValidator(r'^\d{9,11}$', 'Enter 9 to 11 digits.')
ntn_validator = RegexValidator(r'^(\d{7,8}|\d{13})$', 'Enter a 7-8 digit NTN or a 13-digit CNIC-based NTN.')
