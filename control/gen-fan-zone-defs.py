#!/usr/bin/env python

"""
This script reads in fan definition and zone definition YAML
files and generates a set of structures for use by the fan control code.
"""

import os
import sys
import yaml
from argparse import ArgumentParser
from mako.template import Template

tmpl = '''\
<%!
def indent(str, depth):
    return ''.join(4*' '*depth+line for line in str.splitlines(True))
%>\
<%def name="genHandler(sig)" buffered="True">
%if ('type' in sig['sparams']) and \
    (sig['sparams']['type'] is not None):
${sig['signal']}<${sig['sparams']['type']}>(
%else:
${sig['signal']}(
%endif
%for spk in sig['sparams']['params']:
${sig['sparams'][spk]},
%endfor
%if ('type' in sig['hparams']) and \
    (sig['hparams']['type'] is not None):
handler::${sig['handler']}<${sig['hparams']['type']}>(
%else:
handler::${sig['handler']}(
%endif
%for i, hpk in enumerate(sig['hparams']['params']):
    %if (i+1) != len(sig['hparams']['params']):
    ${sig['hparams'][hpk]},
    %else:
    ${sig['hparams'][hpk]}
    %endif
%endfor
))
</%def>\
<%def name="genSSE(event)" buffered="True">
Group{
%for member in event['group']:
{
    "${member['object']}",
    {"${member['interface']}",
     "${member['property']}"}
},
%endfor
},
std::vector<Action>{
%for a in event['action']:
%if len(a['parameters']) != 0:
make_action(action::${a['name']}(
%else:
make_action(action::${a['name']}
%endif
%for i, p in enumerate(a['parameters']):
%if (i+1) != len(a['parameters']):
    static_cast<${p['type']}>(${p['value']}),
%else:
    static_cast<${p['type']}>(${p['value']}))
%endif
%endfor
),
%endfor
},
Timer{
    ${event['timer']['interval']}
},
std::vector<Signal>{
%for s in event['signals']:
    Signal{
        match::${s['match']}(
        %for i, mp in enumerate(s['mparams']):
        %if (i+1) != len(s['mparams']):
        "${mp}",
        %else:
        "${mp}"
        %endif
        %endfor
        ),
        make_handler(\
        ${indent(genHandler(sig=s), 3)}\
        )
    },
%endfor
}
</%def>\
/* This is a generated file. */
#include "manager.hpp"
#include "functor.hpp"
#include "actions.hpp"
#include "handlers.hpp"
#include "preconditions.hpp"
#include "matches.hpp"

using namespace phosphor::fan::control;

const unsigned int Manager::_powerOnDelay{${mgr_data['power_on_delay']}};

const std::vector<ZoneGroup> Manager::_zoneLayouts
{
%for zone_group in zones:
    ZoneGroup{
        std::vector<Condition>{
        %for condition in zone_group['conditions']:
            Condition{
                "${condition['type']}",
                std::vector<ConditionProperty>{
                %for property in condition['properties']:
                    ConditionProperty{
                        "${property['property']}",
                        "${property['interface']}",
                        "${property['path']}",
                        static_cast<${property['type']}>(${property['value']}),
                    },
                    %endfor
                },
            },
            %endfor
        },
        std::vector<ZoneDefinition>{
        %for zone in zone_group['zones']:
            ZoneDefinition{
                ${zone['num']},
                ${zone['full_speed']},
                ${zone['default_floor']},
                ${zone['increase_delay']},
                ${zone['decrease_interval']},
                std::vector<FanDefinition>{
                %for fan in zone['fans']:
                    FanDefinition{
                        "${fan['name']}",
                        std::vector<std::string>{
                        %for sensor in fan['sensors']:
                            "${sensor}",
                        %endfor
                        }
                    },
                %endfor
                },
                std::vector<SetSpeedEvent>{
                %for event in zone['events']:
                    %if ('pc' in event) and \
                        (event['pc'] is not None):
                    SetSpeedEvent{
                        Group{
                        %for member in event['pc']['pcgrp']:
                        {
                            "${member['object']}",
                            {"${member['interface']}",
                             "${member['property']}"}
                        },
                        %endfor
                        },
                        std::vector<Action>{
                        %for i, a in enumerate(event['pc']['pcact']):
                        %if len(a['params']) != 0:
                        make_action(
                            precondition::${a['name']}(
                        %else:
                        make_action(
                            precondition::${a['name']}
                        %endif
                        %for p in a['params']:
                        ${p['type']}${p['open']}
                        %for j, v in enumerate(p['values']):
                        %if (j+1) != len(p['values']):
                            ${v['value']},
                        %else:
                            ${v['value']}
                        %endif
                        %endfor
                        ${p['close']},
                        %endfor
                        %if (i+1) != len(event['pc']['pcact']):
                        %if len(a['params']) != 0:
                        )),
                        %else:
                        ),
                        %endif
                        %endif
                        %endfor
                    std::vector<SetSpeedEvent>{
                    %for pcevt in event['pc']['pcevts']:
                    SetSpeedEvent{\
                    ${indent(genSSE(event=pcevt), 6)}\
                    },
                    %endfor
                    %else:
                    SetSpeedEvent{\
                    ${indent(genSSE(event=event), 6)}
                    %endif
                    %if ('pc' in event) and (event['pc'] is not None):
                    }
                        %if len(event['pc']['pcact'][-1]['params']) != 0:
                        )),
                        %else:
                        ),
                        %endif
                        },
                        Timer{
                            ${event['pc']['pctime']['interval']}
                        },
                        std::vector<Signal>{
                        %for s in event['pc']['pcsigs']:
                            Signal{
                                match::${s['match']}(
                                %for i, mp in enumerate(s['mparams']):
                                %if (i+1) != len(s['mparams']):
                                "${mp}",
                                %else:
                                "${mp}"
                                %endif
                                %endfor
                                ),
                                make_handler(\
                                ${indent(genHandler(sig=s), 9)}\
                                )
                            },
                        %endfor
                        }
                    %endif
                    },
                %endfor
                }
            },
        %endfor
        }
    },
%endfor
};
'''


def convertToMap(listOfDict):
    """
    Converts a list of dictionary entries to a std::map initialization list.
    """
    listOfDict = listOfDict.replace('[', '{')
    listOfDict = listOfDict.replace(']', '}')
    listOfDict = listOfDict.replace(':', ',')
    return listOfDict


def getEvent(zone_num, zone_conditions, e, events_data):
    """
    Parses the sections of an event and populates the properties
    that construct an event within the generated source.
    """
    event = {}
    # Zone numbers are optional in the events yaml but skip if this
    # zone's zone number is not in the event's zone numbers
    if all('zones' in z and
           z['zones'] is not None and
           zone_num not in z['zones']
           for z in e['zone_conditions']):
        return

    # Zone conditions are optional in the events yaml but skip
    # if this event's condition is not in this zone's conditions
    if all('name' in z and z['name'] is not None and
           not any(c['name'] == z['name'] for c in zone_conditions)
           for z in e['zone_conditions']):
        return

    # Add set speed event group
    group = []
    groups = next(g for g in events_data['groups']
                  if g['name'] == e['group'])
    for member in groups['members']:
        members = {}
        members['object'] = (groups['type'] +
                             member)
        members['interface'] = e['interface']
        members['property'] = e['property']['name']
        members['type'] = e['property']['type']
        group.append(members)
    event['group'] = group

    # Add set speed actions and function parameters
    action = []
    for eActions in e['actions']:
        actions = {}
        eAction = next(a for a in events_data['actions']
                       if a['name'] == eActions['name'])
        actions['name'] = eAction['name']
        params = []
        if ('parameters' in eAction) and \
           (eAction['parameters'] is not None):
            for p in eAction['parameters']:
                param = {}
                if type(eActions[p]) is not dict:
                    if p == 'property':
                        param['value'] = str(eActions[p]).lower()
                        param['type'] = str(
                            e['property']['type']).lower()
                    else:
                        # Default type to 'size_t' when not given
                        param['value'] = str(eActions[p]).lower()
                        param['type'] = 'size_t'
                    params.append(param)
                else:
                    param['type'] = str(eActions[p]['type']).lower()
                    if p != 'map':
                        param['value'] = str(
                            eActions[p]['value']).lower()
                    else:
                        emap = convertToMap(str(eActions[p]['value']))
                        param['value'] = param['type'] + emap
                    params.append(param)
        actions['parameters'] = params
        action.append(actions)
    event['action'] = action

    # Add signal handlers
    signals = []
    for member in group:
        for eMatches in e['matches']:
            signal = {}
            eMatch = next(m for m in events_data['matches']
                          if m['name'] == eMatches['name'])
            signal['match'] = eMatch['name']
            params = []
            if ('parameters' in eMatch) and \
               (eMatch['parameters'] is not None):
                for p in eMatch['parameters']:
                    params.append(member[str(p)])
            signal['mparams'] = params
            eSignal = next(s for s in events_data['signals']
                           if s['name'] == eMatch['signal'])
            signal['signal'] = eSignal['name']
            sparams = {}
            if ('parameters' in eSignal) and \
               (eSignal['parameters'] is not None):
                splist = []
                for p in eSignal['parameters']:
                    sp = str(p)
                    if (sp != 'type'):
                        splist.append(sp)
                        if (sp != 'group'):
                            sparams[sp] = "\"" + member[sp] + "\""
                        else:
                            sparams[sp] = "Group{\n"
                            for m in group:
                                sparams[sp] += (
                                    "{\n" +
                                    "\"" + str(m['object']) + "\",\n" +
                                    "{\"" + str(m['interface']) + "\"," +
                                    "\"" + str(m['property']) + "\"}\n" +
                                    "},\n")
                            sparams[sp] += "}"
                    else:
                        sparams[sp] = member[sp]
                sparams['params'] = splist
            signal['sparams'] = sparams
            # Add signal handler
            eHandler = next(h for h in events_data['handlers']
                            if h['name'] == eSignal['handler'])
            signal['handler'] = eHandler['name']
            hparams = {}
            if ('parameters' in eHandler) and \
               (eHandler['parameters'] is not None):
                hplist = []
                for p in eHandler['parameters']:
                    hp = str(p)
                    if (hp != 'type'):
                        hplist.append(hp)
                        if (hp != 'group'):
                            hparams[hp] = "\"" + member[hp] + "\""
                        else:
                            hparams[hp] = "Group{\n"
                            for m in group:
                                hparams[hp] += (
                                    "{\n" +
                                    "\"" + str(m['object']) + "\",\n" +
                                    "{\"" + str(m['interface']) + "\"," +
                                    "\"" + str(m['property']) + "\"}\n" +
                                    "},\n")
                            hparams[hp] += "}"
                    else:
                        hparams[hp] = member[hp]
                hparams['params'] = hplist
            signal['hparams'] = hparams
            signals.append(signal)
    event['signals'] = signals

    # Add optional action call timer
    timer = {}
    interval = "static_cast<std::chrono::seconds>"
    if ('timer' in e) and \
       (e['timer'] is not None):
        timer['interval'] = (interval +
                             "(" +
                             str(e['timer']['interval']) +
                             ")")
    else:
        timer['interval'] = (interval +
                             "(" + str(0) + ")")
    event['timer'] = timer

    return event


def addPrecondition(zNum, zCond, event, events_data):
    """
    Parses the precondition section of an event and populates the necessary
    structures to generate a precondition for a set speed event.
    """
    precond = {}
    # Add set speed event precondition group
    group = []
    for grp in event['precondition']['groups']:
        groups = next(g for g in events_data['groups']
                      if g['name'] == grp['name'])
        for member in groups['members']:
            members = {}
            members['object'] = (groups['type'] +
                                 member)
            members['interface'] = grp['interface']
            members['property'] = grp['property']['name']
            members['type'] = grp['property']['type']
            members['value'] = grp['property']['value']
            group.append(members)
    precond['pcgrp'] = group

    # Add set speed event precondition actions
    pc = []
    pcs = {}
    pcs['name'] = event['precondition']['name']
    epc = next(p for p in events_data['preconditions']
               if p['name'] == event['precondition']['name'])
    params = []
    for p in epc['parameters']:
        param = {}
        if p == 'groups':
            param['type'] = "std::vector<PrecondGroup>"
            param['open'] = "{"
            param['close'] = "}"
            values = []
            for pcgrp in group:
                value = {}
                value['value'] = (
                    "PrecondGroup{\"" +
                    str(pcgrp['object']) + "\",\"" +
                    str(pcgrp['interface']) + "\",\"" +
                    str(pcgrp['property']) + "\"," +
                    "static_cast<" +
                    str(pcgrp['type']).lower() + ">" +
                    "(" + str(pcgrp['value']).lower() + ")}")
                values.append(value)
            param['values'] = values
        params.append(param)
    pcs['params'] = params
    pc.append(pcs)
    precond['pcact'] = pc

    pcevents = []
    for pce in event['precondition']['events']:
        pcevent = getEvent(zNum, zCond, pce, events_data)
        if not pcevent:
            continue
        pcevents.append(pcevent)
    precond['pcevts'] = pcevents

    # Add precondition signal handlers
    signals = []
    for member in group:
        for eMatches in event['precondition']['matches']:
            signal = {}
            eMatch = next(m for m in events_data['matches']
                          if m['name'] == eMatches['name'])
            signal['match'] = eMatch['name']
            params = []
            if ('parameters' in eMatch) and \
               (eMatch['parameters'] is not None):
                for p in eMatch['parameters']:
                    params.append(member[str(p)])
            signal['mparams'] = params
            eSignal = next(s for s in events_data['signals']
                           if s['name'] == eMatch['signal'])
            signal['signal'] = eSignal['name']
            sparams = {}
            if ('parameters' in eSignal) and \
               (eSignal['parameters'] is not None):
                splist = []
                for p in eSignal['parameters']:
                    sp = str(p)
                    if (sp != 'type'):
                        splist.append(sp)
                        if (sp != 'group'):
                            sparams[sp] = "\"" + member[sp] + "\""
                        else:
                            sparams[sp] = "Group{\n"
                            for m in group:
                                sparams[sp] += (
                                    "{\n" +
                                    "\"" + str(m['object']) + "\",\n" +
                                    "{\"" + str(m['interface']) + "\"," +
                                    "\"" + str(m['property']) + "\"}\n" +
                                    "},\n")
                            sparams[sp] += "}"
                    else:
                        sparams[sp] = member[sp]
                sparams['params'] = splist
            signal['sparams'] = sparams
            # Add signal handler
            eHandler = next(h for h in events_data['handlers']
                            if h['name'] == eSignal['handler'])
            signal['handler'] = eHandler['name']
            hparams = {}
            if ('parameters' in eHandler) and \
               (eHandler['parameters'] is not None):
                hplist = []
                for p in eHandler['parameters']:
                    hp = str(p)
                    if (hp != 'type'):
                        hplist.append(hp)
                        if (hp != 'group'):
                            hparams[hp] = "\"" + member[hp] + "\""
                        else:
                            hparams[hp] = "Group{\n"
                            for m in group:
                                hparams[hp] += (
                                    "{\n" +
                                    "\"" + str(m['object']) + "\",\n" +
                                    "{\"" + str(m['interface']) + "\"," +
                                    "\"" + str(m['property']) + "\"}\n" +
                                    "},\n")
                            hparams[hp] += "}"
                    else:
                        hparams[hp] = member[hp]
                hparams['params'] = hplist
            signal['hparams'] = hparams
            signals.append(signal)
    precond['pcsigs'] = signals

    # Add optional action call timer
    timer = {}
    interval = "static_cast<std::chrono::seconds>"
    if ('timer' in event['precondition']) and \
       (event['precondition']['timer'] is not None):
        timer['interval'] = (interval +
                             "(" +
                             str(event['precondition']['timer']['interval']) +
                             ")")
    else:
        timer['interval'] = (interval +
                             "(" + str(0) + ")")
    precond['pctime'] = timer

    return precond


def getEventsInZone(zone_num, zone_conditions, events_data):
    """
    Constructs the event entries defined for each zone using the events yaml
    provided.
    """
    events = []

    if 'events' in events_data:
        for e in events_data['events']:
            event = {}
            # Add precondition if given
            if ('precondition' in e) and \
               (e['precondition'] is not None):
                event['pc'] = addPrecondition(zone_num,
                                              zone_conditions,
                                              e,
                                              events_data)
            else:
                event = getEvent(zone_num, zone_conditions, e, events_data)
                if not event:
                    continue
            events.append(event)

    return events


def getFansInZone(zone_num, profiles, fan_data):
    """
    Parses the fan definition YAML files to find the fans
    that match both the zone passed in and one of the
    cooling profiles.
    """

    fans = []

    for f in fan_data['fans']:

        if zone_num != f['cooling_zone']:
            continue

        # 'cooling_profile' is optional (use 'all' instead)
        if f.get('cooling_profile') is None:
            profile = "all"
        else:
            profile = f['cooling_profile']

        if profile not in profiles:
            continue

        fan = {}
        fan['name'] = f['inventory']
        fan['sensors'] = f['sensors']
        fans.append(fan)

    return fans


def getConditionInZoneConditions(zone_condition, zone_conditions_data):
    """
    Parses the zone conditions definition YAML files to find the condition
    that match both the zone condition passed in.
    """

    condition = {}

    for c in zone_conditions_data['conditions']:

        if zone_condition != c['name']:
            continue
        condition['type'] = c['type']
        properties = []
        for p in c['properties']:
            property = {}
            property['property'] = p['property']
            property['interface'] = p['interface']
            property['path'] = p['path']
            property['type'] = p['type'].lower()
            property['value'] = str(p['value']).lower()
            properties.append(property)
        condition['properties'] = properties

        return condition


def buildZoneData(zone_data, fan_data, events_data, zone_conditions_data):
    """
    Combines the zone definition YAML and fan
    definition YAML to create a data structure defining
    the fan cooling zones.
    """

    zone_groups = []

    for group in zone_data:
        conditions = []
        # zone conditions are optional
        if 'zone_conditions' in group and group['zone_conditions'] is not None:
            for c in group['zone_conditions']:

                if not zone_conditions_data:
                    sys.exit("No zone_conditions YAML file but " +
                             "zone_conditions used in zone YAML")

                condition = getConditionInZoneConditions(c['name'],
                                                         zone_conditions_data)

                if not condition:
                    sys.exit("Missing zone condition " + c['name'])

                conditions.append(condition)

        zone_group = {}
        zone_group['conditions'] = conditions

        zones = []
        for z in group['zones']:
            zone = {}

            # 'zone' is required
            if ('zone' not in z) or (z['zone'] is None):
                sys.exit("Missing fan zone number in " + zone_yaml)

            zone['num'] = z['zone']

            zone['full_speed'] = z['full_speed']

            zone['default_floor'] = z['default_floor']

            # 'increase_delay' is optional (use 0 by default)
            key = 'increase_delay'
            zone[key] = z.setdefault(key, 0)

            # 'decrease_interval' is optional (use 0 by default)
            key = 'decrease_interval'
            zone[key] = z.setdefault(key, 0)

            # 'cooling_profiles' is optional (use 'all' instead)
            if ('cooling_profiles' not in z) or \
                    (z['cooling_profiles'] is None):
                profiles = ["all"]
            else:
                profiles = z['cooling_profiles']

            fans = getFansInZone(z['zone'], profiles, fan_data)
            events = getEventsInZone(z['zone'], group['zone_conditions'],
                                     events_data)

            if len(fans) == 0:
                sys.exit("Didn't find any fans in zone " + str(zone['num']))

            zone['fans'] = fans
            zone['events'] = events
            zones.append(zone)

        zone_group['zones'] = zones
        zone_groups.append(zone_group)

    return zone_groups


if __name__ == '__main__':
    parser = ArgumentParser(
        description="Phosphor fan zone definition parser")

    parser.add_argument('-z', '--zone_yaml', dest='zone_yaml',
                        default="example/zones.yaml",
                        help='fan zone definitional yaml')
    parser.add_argument('-f', '--fan_yaml', dest='fan_yaml',
                        default="example/fans.yaml",
                        help='fan definitional yaml')
    parser.add_argument('-e', '--events_yaml', dest='events_yaml',
                        help='events to set speeds yaml')
    parser.add_argument('-c', '--zone_conditions_yaml',
                        dest='zone_conditions_yaml',
                        help='conditions to determine zone yaml')
    parser.add_argument('-o', '--output_dir', dest='output_dir',
                        default=".",
                        help='output directory')
    args = parser.parse_args()

    if not args.zone_yaml or not args.fan_yaml:
        parser.print_usage()
        sys.exit(-1)

    with open(args.zone_yaml, 'r') as zone_input:
        zone_data = yaml.safe_load(zone_input) or {}

    with open(args.fan_yaml, 'r') as fan_input:
        fan_data = yaml.safe_load(fan_input) or {}

    events_data = {}
    if args.events_yaml:
        with open(args.events_yaml, 'r') as events_input:
            events_data = yaml.safe_load(events_input) or {}

    zone_conditions_data = {}
    if args.zone_conditions_yaml:
        with open(args.zone_conditions_yaml, 'r') as zone_conditions_input:
            zone_conditions_data = yaml.safe_load(zone_conditions_input) or {}

    zone_config = buildZoneData(zone_data.get('zone_configuration', {}),
                                fan_data, events_data, zone_conditions_data)

    manager_config = zone_data.get('manager_configuration', {})

    if manager_config.get('power_on_delay') is None:
        manager_config['power_on_delay'] = 0

    output_file = os.path.join(args.output_dir, "fan_zone_defs.cpp")
    with open(output_file, 'w') as output:
        output.write(Template(tmpl).render(zones=zone_config,
                     mgr_data=manager_config))
