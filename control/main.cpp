/**
 * Copyright © 2017 IBM Corporation
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
#include <sdbusplus/bus.hpp>
#include <phosphor-logging/log.hpp>
#include "argument.hpp"
#include "manager.hpp"
#include "event.hpp"
#include "sdbusplus.hpp"

using namespace phosphor::fan::control;
using namespace phosphor::logging;

int main(int argc, char* argv[])
{
    auto bus = sdbusplus::bus::new_default();
    sd_event* events = nullptr;
    phosphor::fan::util::ArgumentParser args(argc, argv);

    if (argc != 2)
    {
        args.usage(argv);
        exit(-1);
    }

    Mode mode;

    if (args["init"] == "true")
    {
        mode = Mode::init;
    }
    else if (args["control"] == "true")
    {
        mode = Mode::control;
    }
    else
    {
        args.usage(argv);
        exit(-1);
    }

    auto r = sd_event_default(&events);
    if (r < 0)
    {
        log<level::ERR>("Failed call to sd_event_default()",
                        entry("ERROR=%s", strerror(-r)));
        return -1;
    }

    phosphor::fan::event::EventPtr eventPtr{events};

    //Attach the event object to the bus object so we can
    //handle both sd_events (for the timers) and dbus signals.
    bus.attach_event(eventPtr.get(), SD_EVENT_PRIORITY_NORMAL);

    try
    {
        Manager manager(bus, eventPtr, mode);

        //Init mode will just set fans to max and delay
        if (mode == Mode::init)
        {
            manager.doInit();
            return 0;
        }
        else
        {
            r = sd_event_loop(eventPtr.get());
            if (r < 0)
            {
                log<level::ERR>("Failed call to sd_event_loop",
                        entry("ERROR=%s", strerror(-r)));
            }
        }
    }
    //Log the useful metadata on these exceptions and let the app
    //return -1 so it is restarted without a core dump.
    catch (phosphor::fan::util::DBusServiceError& e)
    {
        log<level::ERR>("Uncaught DBus service lookup failure exception",
                entry("PATH=%s", e.path.c_str()),
                entry("INTERFACE=%s", e.interface.c_str()));
    }
    catch (phosphor::fan::util::DBusMethodError& e)
    {
        log<level::ERR>("Uncaught DBus method failure exception",
                entry("BUSNAME=%s", e.busName.c_str()),
                entry("PATH=%s", e.path.c_str()),
                entry("INTERFACE=%s", e.interface.c_str()),
                entry("METHOD=%s", e.method.c_str()));
    }
    catch (phosphor::fan::util::DBusPropertyError& e)
    {
        log<level::ERR>("Uncaught DBus property access failure exception",
                entry("BUSNAME=%s", e.busName.c_str()),
                entry("PATH=%s", e.path.c_str()),
                entry("INTERFACE=%s", e.interface.c_str()),
                entry("PROPERTY=%s", e.property.c_str()));
    }

    return -1;
}
