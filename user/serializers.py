from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from .models import UserProfile, Organization, OrganizationMember, DashboardTemplate, TemplatePermission, Project


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name')


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(style={'input_type': 'password'})

    def validate(self, data):
        email = data.get('email')
        password = data.get('password')

        if email and password:
            # Try to authenticate using email as username
            user = authenticate(username=email, password=password)
            
            if not user:
                # Try to find user by email and authenticate with username
                try:
                    user_obj = User.objects.get(email=email)
                    user = authenticate(username=user_obj.username, password=password)
                except User.DoesNotExist:
                    user = None
            
            if user:
                if not user.is_active:
                    raise serializers.ValidationError('User account is disabled.')
                data['user'] = user
            else:
                raise serializers.ValidationError('Invalid email or password.')
        else:
            raise serializers.ValidationError('Must include email and password.')

        return data


class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    password_confirm = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'password_confirm', 'first_name', 'last_name')

    def validate(self, attrs):
        # Add password_confirm if not provided (for encrypted requests)
        if 'password_confirm' not in attrs:
            attrs['password_confirm'] = attrs['password']
        
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        
        if User.objects.filter(email=attrs['email']).exists():
            raise serializers.ValidationError("User with this email already exists.")
        
        if User.objects.filter(username=attrs['username']).exists():
            raise serializers.ValidationError("User with this username already exists.")
        
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        
        # Create user profile safely
        UserProfile.objects.get_or_create(
            user=user,
            defaults={'subscription_type': 'free'}
        )
        
        return user


class OrganizationSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    admin_count = serializers.SerializerMethodField()
    user_count = serializers.SerializerMethodField()
    project_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Organization
        fields = ('id', 'name', 'description', 'owner', 'slug', 'is_active', 
                 'created_at', 'updated_at', 'admin_count', 'user_count', 'project_count')
        read_only_fields = ('owner', 'created_at', 'updated_at')
    
    def get_admin_count(self, obj):
        return obj.get_admin_count()
    
    def get_user_count(self, obj):
        return obj.get_user_count()
    
    def get_project_count(self, obj):
        return obj.get_project_count()


class OrganizationMemberSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    organization = OrganizationSerializer(read_only=True)
    invited_by = UserSerializer(read_only=True)
    
    class Meta:
        model = OrganizationMember
        fields = ('id', 'organization', 'user', 'role', 'joined_at', 'invited_by')
        read_only_fields = ('joined_at', 'invited_by')


class ProjectSerializer(serializers.ModelSerializer):
    creator = UserSerializer(read_only=True)
    organization = OrganizationSerializer(read_only=True)
    flow_count = serializers.SerializerMethodField()
    dashboard_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Project
        fields = ('uuid', 'id', 'name', 'description', 'organization', 'creator', 
                 'status', 'tags', 'metadata', 'auto_save', 'data_retention_days',
                 'is_active', 'created_at', 'updated_at', 'flow_count', 'dashboard_count')
        read_only_fields = ('creator', 'created_at', 'updated_at')
    
    def get_flow_count(self, obj):
        return obj.get_flow_count()
    
    def get_dashboard_count(self, obj):
        return obj.get_dashboard_count()


class CreateProjectSerializer(serializers.ModelSerializer):
    organization_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = Project
        fields = ('name', 'description', 'organization_id', 'status', 'tags', 
                 'metadata', 'auto_save', 'data_retention_days')
    
    def validate_organization_id(self, value):
        try:
            organization = Organization.objects.get(id=value)
            # Check if user has admin access to this organization
            user = self.context['request'].user
            if not organization.members.filter(user=user, role='admin').exists():
                raise serializers.ValidationError("You don't have admin access to this organization.")
            return value
        except Organization.DoesNotExist:
            raise serializers.ValidationError("Organization not found.")
    
    def create(self, validated_data):
        organization_id = validated_data.pop('organization_id')
        organization = Organization.objects.get(id=organization_id)
        
        validated_data['organization'] = organization
        validated_data['creator'] = self.context['request'].user
        
        return Project.objects.create(**validated_data)


class DashboardTemplateSerializer(serializers.ModelSerializer):
    creator = UserSerializer(read_only=True)
    organization = OrganizationSerializer(read_only=True)
    project = ProjectSerializer(read_only=True)
    admin_count = serializers.SerializerMethodField()
    user_count = serializers.SerializerMethodField()
    
    class Meta:
        model = DashboardTemplate
        fields = ('uuid', 'id', 'name', 'description', 'organization', 'project', 'creator', 
                 'layout', 'widgets', 'datasources', 'update_frequency', 
                 'connection_timeout', 'flow_config', 'is_active', 
                 'created_at', 'updated_at', 'admin_count', 'user_count')
        read_only_fields = ('creator', 'created_at', 'updated_at')
    
    def get_admin_count(self, obj):
        return obj.get_admin_count()
    
    def get_user_count(self, obj):
        return obj.get_user_count()


class TemplatePermissionSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    template = DashboardTemplateSerializer(read_only=True)
    granted_by = UserSerializer(read_only=True)
    
    class Meta:
        model = TemplatePermission
        fields = ('id', 'template', 'user', 'permission_type', 'granted_by', 'granted_at')
        read_only_fields = ('granted_by', 'granted_at')


class CreateOrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ('name', 'description')
    
    def validate_name(self, value):
        if Organization.objects.filter(name=value).exists():
            raise serializers.ValidationError("An organization with this name already exists.")
        return value
    
    def create(self, validated_data):
        import time
        from django.utils.text import slugify
        
        # Set the owner to the current user
        validated_data['owner'] = self.context['request'].user
        
        # Auto-generate unique slug
        base_slug = slugify(validated_data['name'])
        if not base_slug:  # If name contains no valid characters for slug
            base_slug = f"org-{int(time.time() * 1000)}"
        
        slug = base_slug
        counter = 1
        while Organization.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        
        validated_data['slug'] = slug
        organization = Organization.objects.create(**validated_data)
        
        # Automatically add the owner as an admin member
        OrganizationMember.objects.create(
            organization=organization,
            user=organization.owner,
            role='admin'
        )
        
        return organization


class CreateDashboardTemplateSerializer(serializers.ModelSerializer):
    organization_id = serializers.IntegerField(write_only=True)
    project_id = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = DashboardTemplate
        fields = ('name', 'description', 'organization_id', 'project_id', 'layout', 'widgets', 
                 'datasources', 'update_frequency', 'connection_timeout', 'flow_config')
    
    def validate_organization_id(self, value):
        try:
            organization = Organization.objects.get(id=value)
            # Check if user has admin access to this organization
            user = self.context['request'].user
            if not organization.members.filter(user=user, role='admin').exists():
                raise serializers.ValidationError("You don't have admin access to this organization.")
            return value
        except Organization.DoesNotExist:
            raise serializers.ValidationError("Organization not found.")
    
    def validate_project_id(self, value):
        if value:
            try:
                project = Project.objects.get(id=value)
                # Check if user has access to this project
                user = self.context['request'].user
                if not project.organization.members.filter(user=user, role__in=['admin', 'user']).exists():
                    raise serializers.ValidationError("You don't have access to this project.")
                return value
            except Project.DoesNotExist:
                raise serializers.ValidationError("Project not found.")
        return value
    
    def create(self, validated_data):
        organization_id = validated_data.pop('organization_id')
        project_id = validated_data.pop('project_id', None)
        
        organization = Organization.objects.get(id=organization_id)
        validated_data['organization'] = organization
        validated_data['creator'] = self.context['request'].user
        
        if project_id:
            project = Project.objects.get(id=project_id)
            validated_data['project'] = project
        
        return DashboardTemplate.objects.create(**validated_data) 