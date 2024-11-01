from app import db

class Gift(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(100))
    affiliate_link = db.Column(db.String(500))
    source = db.Column(db.String(100))  # e.g., 'buyagift', 'database'
    tags = db.Column(db.String(500))  # Store as comma-separated values
    image_path = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'price': self.price,
            'category': self.category,
            'affiliate_link': self.affiliate_link,
            'tags': self.tags.split(',') if self.tags else [],
            'image_path': self.image_path  # Add this line
        } 