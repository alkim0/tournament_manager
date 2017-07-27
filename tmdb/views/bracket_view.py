"""
Bracket View

Last Updated: 07-09-2017
"""

import json

from django.shortcuts import redirect, render, get_object_or_404
from django.core import serializers
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseForbidden
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth import models as auth_models
from django.contrib import messages

from tmdb import forms
import tmdb.models as models

from collections import defaultdict
import datetime

from tmdb.util.bracket_svg import SvgBracket


def blue_team_text(team_match):
    if team_match.blue_team is None:
        return None
    return team_match.blue_team.bracket_str()


def red_team_text(team_match):
    if team_match.red_team is None:
        return None
    return team_match.red_team.bracket_str()


def bracket_printable(request, tournament_slug, division_slug):
    tournament = get_object_or_404(models.Tournament, slug=tournament_slug)
    tournament_division = get_object_or_404(models.TournamentDivision,
            tournament=tournament, division__slug=division_slug)
    matches, num_rounds = models.TeamMatch.get_matches_by_round(
            tournament_division)
    bracket_columns = []
    for round_num in reversed(range(num_rounds + 1)):
        round_num_matches = 2**round_num
        bracket_column = [None] * round_num_matches
        bracket_columns.append(bracket_column)
        for round_slot in range(round_num_matches):
            key = (round_num, round_slot)
            if key not in matches:
                continue
            bracket_column[round_slot] = matches[key]
    bracket = SvgBracket.create(bracket_columns,
            blue_team_text=blue_team_text, red_team_text=red_team_text)
    response = '<html><body>%s</body></html>' %(bracket.tostring(
            encoding="unicode"),)
    return HttpResponse(response, content_type="image/svg+xml")

def bracket(request, tournament_slug, division_slug):
    tournament = get_object_or_404(models.Tournament, slug=tournament_slug)
    tournament_division = get_object_or_404(models.TournamentDivision,
            tournament=tournament, division__slug=division_slug)
    bracket_columns = []
    matches, num_rounds = models.TeamMatch.get_matches_by_round(
            tournament_division)
    bracket_column_height = str(64 * 2**num_rounds) + "px"
    for round_num in reversed(range(num_rounds + 1)):
        round_num_matches = 2**round_num
        bracket_column = [None] * round_num_matches
        bracket_columns.append(bracket_column)
        for round_slot in range(round_num_matches):
            key = (round_num, round_slot)
            cell_type = []
            if key not in matches:
                match = models.TeamMatch()
                cell_type.append("bracket_cell_without_match")
            else:
                match = matches[key]
                cell_type.append("bracket_cell_with_match")
            if round_slot % 2:
                cell_type.append("lower_child_cell")
            else:
                cell_type.append("upper_child_cell")
            bracket_column[round_slot] = match
            match.cell_type = " ".join(cell_type)
            match.height = str(100 / (round_num_matches)) + "%"
    if (0, 0) in matches:
        matches[(0, 0)].cell_type = "bracket_cell_with_match" \
                + " bracket_finals_cell"
    unassigned_teams = models.TeamRegistration.get_teams_without_assigned_slot(
            tournament_division)

    context = {
            'tournament_division': tournament_division,
            'tournament': tournament,
            'bracket_columns': bracket_columns,
            'bracket_column_height': bracket_column_height,
            'unassigned_teams': unassigned_teams,
            'lowest_bye_seed': get_lowest_bye_seed(tournament_division),
    }
    return render(request, 'tmdb/brackets.html', context)

def get_lowest_bye_seed(tournament_division):
    team_registrations = models.TeamRegistration.objects.filter(
            tournament_division=tournament_division)
    team_matches = models.TeamMatch.objects.filter(
            division=tournament_division).order_by('-round_num')
    if not team_matches:
        return 1
    max_round_num = team_matches[0].round_num
    seeds = {tr.seed for tr in team_registrations if tr.seed}
    max_seed = max(seeds)
    for team_match in team_matches:
        if team_match.round_num != max_round_num:
            break
        if team_match.blue_team:
            seeds.remove(team_match.blue_team.seed)
        if team_match.red_team:
            seeds.remove(team_match.red_team.seed)
    if not seeds:
        return max_seed
    return max(seeds)


@permission_required("tmdb.add_teammatch")
def add_team_to_bracket(request, tournament_slug, division_slug):
    if request.method == 'POST':
        form = forms.TeamRegistrationSeedingForm(request.POST)
        if form.is_valid():
            team_registration = models.TeamRegistration.objects.get(
                    pk=request.POST['team_registration'])
            team_registration.seed = int(request.POST['seed'])
            team_registration.save()
            tournament_division = team_registration.tournament_division
            models.TeamMatch.create_matches_from_slots(tournament_division)
            return HttpResponseRedirect(reverse("tmdb:bracket", args=(
                    tournament_division.tournament.slug,
                    tournament_division.division.slug,)))
    else:
        side = request.GET.get('side')
        round_num = request.GET.get('round_num')
        round_slot = request.GET.get('round_slot')
        tournament_division = get_object_or_404(models.TournamentDivision,
                tournament__slug=tournament_slug, division__slug=division_slug)
        existing_match = get_object_or_404(models.TeamMatch,
                division=tournament_division, round_num=round_num,
                round_slot=round_slot)
        if side == "upper":
            existing_team = existing_match.blue_team
        elif side == "lower":
            existing_team = existing_match.red_team
        else:
            raise ValueError("side was `%s`, must be `upper` or `lower`" %(
                    side,))
        new_seed = 2**(int(round_num) + 2) - existing_team.seed + 1
        form = forms.TeamRegistrationSeedingForm(initial={'seed': new_seed})
        form.fields['team_registration'].queryset = \
                models.TeamRegistration.get_teams_without_assigned_slot(
                        tournament_division)
    context = {
            'tournament_division': tournament_division,
            'tournament': tournament_division.tournament,
            'existing_team': existing_team,
            'new_seed': new_seed,
            'form': form,
    }
    return render(request, 'tmdb/modify_team_registration_seed.html', context)