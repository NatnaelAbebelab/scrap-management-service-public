from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.http import HttpResponse
from django.template import loader
from django.conf import settings
from django.http import JsonResponse
from datetime import datetime
from rest_framework.decorators import api_view
from .models import Role
from .serializers import RoleSerializer
from django.db.models import Q

# Create your views here.
@api_view(['POST'])
def add_role(request) :
    if request.method == 'POST' :
        name = request.POST.get('name').lower()
        try :
            today = datetime.today().strftime('%Y-%m-%d')
            if Role.objects.filter(name=name).exists() :
                return JsonResponse({'result' : 'error', 'message' : 'role already exists'}, status=400)
            role = Role(
                name=name,
                created_by='logged user',
                created_at=today
            )
            role.save()
            return JsonResponse({'result' : 'success', 'message' : 'role added successfully'}, status=200)
        except Exception as e :
            return JsonResponse({'result' : 'error', 'message' : 'operation failed'}, status=400)
@api_view(['PATCH'])
def update_role(request) :
    if request.method == 'PATCH' :
        _id = request.POST.get('_id')
        name = request.POST.get('name').lower()
        try :
            today = datetime.today().strftime('%Y-%m-%d')
            if Role.objects.filter(Q(name=name),~Q(_id=_id)).exists() :
                return JsonResponse({'result' : 'error', 'message' : 'name already used'}, status=400)
            role = Role.objects.get(_id=_id)
            if name != '' :
                role.name = name
            role.updated_at = today
            role.updated_by = 'logged user'
            role.save()
            return JsonResponse({'result' : 'success', 'message' : 'role updated'}, status=200)
        except Exception as e :
            return JsonResponse({'result' : 'error', 'message' : 'operation failed'}, status=400)
@api_view(['GET'])
def get_roles(request) :
    try :
        roles = Role.objects.all()
        serializer = RoleSerializer(roles, many=True)
        return JsonResponse({
            'result' : 'success',
            'data' : serializer.data
        }, status=200)
    except Exception as e:
        return JsonResponse({
            'result' : 'error',
            'data' : e
        }, status=400)
@api_view(['DELETE'])
def delete_role(request) :
    if request.method == 'DELETE' :
        _id = request.POST.get('_id')
        try:
            if not Role.objects.filter(_id=_id).exists() :
                return JsonResponse({'result' : 'error', 'message' : 'role does not exist'}, status=400)
            Role.objects.filter(_id=_id).first().delete()
            # Think about users role value
            return JsonResponse({'result' : 'success', 'message' : 'role deleted'}, status=200)
        except Exception as e:
            return JsonResponse({'result' : 'error', 'message' : 'operation failed'}, status=400)