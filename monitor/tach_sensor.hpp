#pragma once

#include <chrono>
#include <sdbusplus/bus.hpp>
#include <sdbusplus/server.hpp>
#include "event.hpp"
#include "timer.hpp"

namespace phosphor
{
namespace fan
{
namespace monitor
{

class Fan;

constexpr auto FAN_SENSOR_PATH = "/xyz/openbmc_project/sensors/fan_tach/";

/**
 * The mode fan monitor will run in:
 *   - init - only do the initialization steps
 *   - monitor - run normal monitoring algorithm
 */
enum class Mode
{
    init,
    monitor
};

/**
 * @class TachSensor
 *
 * This class represents the sensor that reads a tach value.
 * It may also support a Target, which is the property used to
 * set a speed.  Since it doesn't necessarily have a Target, it
 * won't for sure know if it is running too slow, so it leaves
 * that determination to other code.
 *
 * This class has a parent Fan object that knows about all
 * sensors for that fan.
 */
class TachSensor
{
    public:

        TachSensor() = delete;
        TachSensor(const TachSensor&) = delete;
        // TachSensor is not moveable since the this pointer is used as systemd
        // callback context.
        TachSensor(TachSensor&&) = delete;
        TachSensor& operator=(const TachSensor&) = delete;
        TachSensor& operator=(TachSensor&&) = delete;
        ~TachSensor() = default;

        /**
         * @brief Constructor
         *
         * @param[in] mode - mode of fan monitor
         * @param[in] bus - the dbus object
         * @param[in] fan - the parent fan object
         * @param[in] id - the id of the sensor
         * @param[in] hasTarget - if the sensor supports
         *                        setting the speed
         * @param[in] factor - the factor of the sensor target
         * @param[in] offset - the offset of the sensor target
         * @param[in] timeout - Normal timeout value to use
         * @param[in] events - sd_event pointer
         */
        TachSensor(Mode mode,
                   sdbusplus::bus::bus& bus,
                   Fan& fan,
                   const std::string& id,
                   bool hasTarget,
                   size_t factor,
                   size_t offset,
                   size_t timeout,
                   phosphor::fan::event::EventPtr& events);

        /**
         * @brief Returns the target speed value
         */
        uint64_t getTarget() const;

        /**
         * @brief Returns the input speed value
         */
        inline int64_t getInput() const
        {
            return _tachInput;
        }

        /**
         * @brief Returns true if sensor has a target
         */
        inline bool hasTarget() const
        {
            return _hasTarget;
        }

        /**
         * @brief Returns the factor of the sensor target
         */
        inline size_t getFactor() const
        {
            return _factor;
        }

        /**
         * @brief Returns the offset of the sensor target
         */
        inline size_t getOffset() const
        {
            return _offset;
        }

        /**
         * Returns true if the hardware behind this
         * sensor is considered working OK/functional.
         */
        inline bool functional() const
        {
            return _functional;
        }

        /**
         * Set the functional status and update inventory to match
         */
        void setFunctional(bool functional);

        /**
         * @brief Says if the timer is running or not
         *
         * @return bool - if timer is currently running
         */
        inline bool timerRunning()
        {
            return _timer.running();
        }

        /**
         * @brief Starts the timer for the amount of time
         *        specified in the constructor
         */
        inline void startTimer()
        {
            _timer.start(
                    getTimeout(),
                    phosphor::fan::util::Timer::TimerType::oneshot);
        }

        /**
         * @brief Stops the timer
         */
        inline void stopTimer()
        {
            _timer.stop();
        }

        /**
         * @brief Returns the timeout value to use for the sensor
         */
        std::chrono::microseconds getTimeout();

        /**
         * Returns the sensor name
         */
        inline const std::string& name() const
        {
            return _name;
        };

    private:

        /**
         * @brief Returns the match string to use for matching
         *        on a properties changed signal.
         */
        std::string getMatchString(const std::string& interface);

        /**
         * @brief Reads the Target property and stores in _tachTarget.
         *        Also calls Fan::tachChanged().
         *
         * @param[in] msg - the dbus message
         */
        void handleTargetChange(sdbusplus::message::message& msg);

        /**
         * @brief Reads the Value property and stores in _tachInput.
         *        Also calls Fan::tachChanged().
         *
         * @param[in] msg - the dbus message
         */
        void handleTachChange(sdbusplus::message::message& msg);

        /**
         * @brief Updates the Functional property in the inventory
         *        for this tach sensor based on the value passed in.
         *
         * @param[in] functional - If the Functional property should
         *                         be set to true or false.
         */
        void updateInventory(bool functional);

        /**
         * @brief the dbus object
         */
        sdbusplus::bus::bus& _bus;

        /**
         * @brief Reference to the parent Fan object
         */
        Fan& _fan;

        /**
         * @brief The name of the sensor, including the full path
         *
         * For example /xyz/openbmc_project/sensors/fan_tach/fan0
         */
        const std::string _name;

        /**
         * @brief The inventory name of the sensor, including the full path
         */
        const std::string _invName;

        /**
         * @brief If functional (not too slow).  The parent
         *        fan object sets this.
         */
        bool _functional;

        /**
         * @brief If the sensor has a Target property (can set speed)
         */
        const bool _hasTarget;

        /**
         * @brief The factor of target to get fan rpm
         */
        const size_t _factor;

        /**
         * @brief The offset of target to get fan rpm
         */
        const size_t _offset;

        /**
         * @brief The input speed, from the Value dbus property
         */
        int64_t _tachInput = 0;

        /**
         * @brief The current target speed, from the Target dbus property
         *        (if applicable)
         */
        uint64_t _tachTarget = 0;

        /**
         * @brief The timeout value to use
         */
        const size_t _timeout;

        /**
         * The timer object
         */
        phosphor::fan::util::Timer _timer;

        /**
         * @brief The match object for the Value properties changed signal
         */
        std::unique_ptr<sdbusplus::server::match::match> tachSignal;

        /**
         * @brief The match object for the Target properties changed signal
         */
        std::unique_ptr<sdbusplus::server::match::match> targetSignal;
};

}
}
}
