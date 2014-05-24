from django.shortcuts import render
from django.shortcuts import get_object_or_404
from django.http import HttpResponseRedirect, HttpResponse
from boxes.models import Box, Idea, Vote, Comment
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.contrib import messages
from django import forms
from boxes import helpers
from boxes import decorators

def join(request, box_pk):
    """Join box via mail"""
    box = get_object_or_404(Box, pk=box_pk)
    if request.method == 'POST':
        if request.POST.get('request-key'):
            email = request.POST.get('email')
            try:
                key = box.email_register(email)
                send_mail('kioto.io: Access code for "%s"' % box.name,key,
                      'no-reply@kioto.io',[email], fail_silently=False)
                messages.add_message(request, messages.SUCCESS, 'Access code sent to %s' % email)
            except ValidationError as e:
                messages.add_message(request, messages.ERROR, e.message)
        else:
            if box.key_valid(request.POST.get('key')):
                keys = request.session.get('boxes_keys',{})
                keys[box.pk] = request.POST.get('key')
                request.session['boxes_keys'] = keys
                return HttpResponseRedirect(box.url())
            else:
                messages.add_message(request, messages.ERROR, 'Invalid access code')

    return render(request, 'box/join.html', { 'box': box, 'hide_logout':True})

@decorators.idea
def idea(request, box_pk, idea_pk, idea=None, user_key=None):
    vote = Vote.objects.filter(idea=idea, user_key=user_key).first()
    if request.method == 'POST':
        comment = Comment(idea=idea, user_key=user_key, content=request.POST.get('content'))
        comment.save()

    if vote:
        idea.user_vote = vote.vote
    return render(request,'box/idea.html',{
        'idea':idea, 
        'box':idea.box,
        'user_key':user_key,
    })

@require_POST
@decorators.box
def logout(request, box_pk, box=None, user_key=None):
    keys = request.session.get('boxes_keys',{})
    if box_pk in keys:
        del keys[box_pk]
    request.session['boxes_keys'] = keys
    return HttpResponseRedirect(box.url())

@require_POST
@decorators.idea
def delete_idea(request, box_pk, idea_pk, idea=None, user_key=None):
    idea.delete()
    return HttpResponseRedirect(idea.box.url())

@require_POST
@decorators.idea
def vote(request, box_pk, idea_pk, vote, idea=None, user_key=None):
    session_key = request.session.session_key
    try:
        current_vote = Vote.objects.get(user_key=session_key, idea=idea)
        current_vote.delete()
    except Vote.DoesNotExist:
        pass
    vote = Vote(idea=idea, user_key=session_key, vote=Vote.from_str(vote))
    vote.save()
    idea.update_cached_score()
    return HttpResponse(str(idea.score()))

@decorators.box
def box(request, box_pk, sort='top', box=None, user_key=None):
    ideas = Idea.objects.filter(box=box) 
    session_key = request.session.session_key
    if request.method == 'POST':
        idea = Idea(box=box, title=request.POST.get('title'), user_key=session_key)
        idea.save()

    if sort is 'top':
        ideas = ideas.order_by('-cached_score','-date')
    elif sort == 'new':
        ideas = ideas.order_by('-date')
    elif sort == 'hot':
        ideas = list(ideas.order_by('-date')[:200])
        for idea in ideas:
            idea.hot_score = idea.compute_hot_score()
        ideas.sort(key=lambda x: x.hot_score, reverse=True)
    

    #pagination
    paginator = Paginator(ideas, 40)
    page = request.GET.get('page')
    try:
        ideas = paginator.page(page)
    except PageNotAnInteger:
        ideas = paginator.page(1)
    except EmptyPage:
        ideas = paginator.page(paginator.num_pages)

    #add user current vote
    votes = Vote.objects.filter(user_key=session_key)
    for idea in ideas:
        for vote in votes:
            if vote.idea_id == idea.pk:
                idea.user_vote = vote.vote

    return render(request,'box/home.html',{
        'box':box,    
        'ideas':ideas,
        'sort':sort,
    })

class SettingsForm(forms.ModelForm): 
    class Meta:
        model = Box
        fields = ('name','access_mode','email_suffix')

@decorators.box
def settings(request, box_pk, box=None):
    form = SettingsForm(instance=box)
    if request.method == 'POST':
        form = SettingsForm(data=request.POST, instance=box)
        if form.is_valid():
            form.save()
    return render(request,'box/settings.html', {
        'box':box,
        'form':form,
        })


def home(request):
    if request.method == 'POST':
        slug = helpers.randascii(6)
        box = Box(slug=slug,name="")
        box.save()
        return HttpResponseRedirect(box.url())
    return render(request,'home.html')

