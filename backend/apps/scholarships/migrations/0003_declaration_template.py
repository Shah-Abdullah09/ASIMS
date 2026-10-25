from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarships', '0002_alter_application_registration_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='declaration',
            name='template',
            field=models.CharField(
                choices=[('self_employed', 'Self owned business / employment / freelance'),
                         ('farmer', 'Farmers only'),
                         ('labourer', 'Labourers and private workers (non-salaried)'),
                         ('employed', 'Employed or pensioner persons')],
                default='employed', max_length=20),
            preserve_default=False,  # one-time value for rows created before this field existed
        ),
    ]
