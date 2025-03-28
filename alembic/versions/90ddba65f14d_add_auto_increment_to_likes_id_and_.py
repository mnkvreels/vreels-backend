"""Add auto-increment to likes id and comments id



Revision ID: 90ddba65f14d
Revises: 46e2e4318bb4
Create Date: 2025-03-28 14:38:20.597475

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql

# revision identifiers, used by Alembic.
revision = '90ddba65f14d'
down_revision = '46e2e4318bb4'
branch_labels = None
depends_on = None


def upgrade():
    # First, check if the 'id' column already exists in the 'likes' table.
    # If it exists, we need to drop the primary key and alter the column.
    # Drop the existing primary key constraint on 'id' column if it exists
    op.execute('''
    IF EXISTS (SELECT 1 FROM sys.key_constraints WHERE parent_object_id = OBJECT_ID('likes') AND type = 'PK')
    BEGIN
        DECLARE @ConstraintName NVARCHAR(128);
        SELECT @ConstraintName = name
        FROM sys.key_constraints
        WHERE parent_object_id = OBJECT_ID('likes') AND type = 'PK';
        EXEC('ALTER TABLE likes DROP CONSTRAINT ' + @ConstraintName);
    END
    ''')

    # Drop the 'id' column if it exists
    op.execute('''
    IF EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'likes' AND COLUMN_NAME = 'id')
    BEGIN
        ALTER TABLE likes DROP COLUMN id;
    END
    ''')

    # Now add the 'id' column with IDENTITY (auto-increment) and PRIMARY KEY constraint
    op.execute('ALTER TABLE likes ADD id INT IDENTITY(1,1) PRIMARY KEY')

    # Alter other columns as necessary
    op.alter_column('likes', 'user_id', existing_type=sa.INTEGER(), nullable=True)
    op.alter_column('likes', 'post_id', existing_type=sa.INTEGER(), nullable=True)

    # Create an index on 'id' if needed
    op.create_index(op.f('ix_likes_id'), 'likes', ['id'], unique=False)

def downgrade():
    # Drop the new 'id' column
    op.execute('ALTER TABLE likes DROP COLUMN id')

    # Recreate the 'id' column as a non-auto-incrementing primary key
    op.execute('ALTER TABLE likes ADD id INT PRIMARY KEY')

    # Drop index on 'id'
    op.drop_index(op.f('ix_likes_id'), table_name='likes')

    # Revert the changes made to other columns
    op.alter_column('likes', 'post_id', existing_type=sa.INTEGER(), nullable=False)
    op.alter_column('likes', 'user_id', existing_type=sa.INTEGER(), nullable=False)

    # Remove the auto-increment setting from the 'id' column (reverting changes)
    op.alter_column('likes', 'id', existing_type=sa.INTEGER(), server_default=None, existing_nullable=False, autoincrement=False)
