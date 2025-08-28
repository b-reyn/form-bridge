#!/bin/bash

# Form-Bridge WordPress Testing Environment Setup

echo "🚀 Setting up WordPress testing environment for Form-Bridge plugin..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p wp-content

# Start Docker containers
echo "🐳 Starting WordPress and MySQL containers..."
docker-compose up -d

# Wait for containers to be ready
echo "⏳ Waiting for containers to start..."
sleep 30

# Check if containers are running
echo "🔍 Checking container status..."
docker-compose ps

# Wait for WordPress to be accessible
echo "🌐 Waiting for WordPress to be accessible..."
until curl -s http://localhost:8080 > /dev/null; do
    echo "   Still waiting for WordPress..."
    sleep 5
done

echo ""
echo "✅ WordPress environment is ready!"
echo ""
echo "🔗 Access URLs:"
echo "   WordPress:    http://localhost:8080"
echo "   phpMyAdmin:   http://localhost:8081"
echo ""
echo "📝 Database Info:"
echo "   Host: localhost:3306"
echo "   Database: wordpress"
echo "   User: wordpress"
echo "   Password: wordpress_password"
echo ""
echo "🔧 WordPress Admin Setup:"
echo "   1. Go to http://localhost:8080"
echo "   2. Complete the WordPress installation"
echo "   3. Recommended settings:"
echo "      Site Title: Form-Bridge Test Site"
echo "      Username: admin"
echo "      Password: admin123"
echo "      Email: admin@localhost"
echo ""
echo "📦 Plugin Installation:"
echo "   The Form-Bridge plugin is automatically mounted at:"
echo "   /wp-content/plugins/form-bridge/"
echo ""
echo "🧪 Testing Steps:"
echo "   1. Complete WordPress setup"
echo "   2. Go to Plugins → Activate 'Form-Bridge Connector'"
echo "   3. Go to Settings → Form-Bridge"
echo "   4. Click 'Test Connection'"
echo "   5. Install Contact Form 7 plugin"
echo "   6. Create a test form and submit it"
echo ""
echo "📋 Debug Info:"
echo "   WordPress debug.log: wp-content/debug.log"
echo "   Container logs: docker-compose logs -f wordpress"
echo ""
echo "🛑 To stop: docker-compose down"
echo "🗑️  To reset: docker-compose down -v (removes all data)"
echo ""

# Show WordPress container logs
echo "📋 Recent WordPress container logs:"
docker-compose logs --tail=10 wordpress

echo ""
echo "🎉 Ready to test Form-Bridge WordPress plugin!"