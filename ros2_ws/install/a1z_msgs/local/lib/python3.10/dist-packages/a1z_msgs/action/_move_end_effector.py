# generated from rosidl_generator_py/resource/_idl.py.em
# with input from a1z_msgs:action/MoveEndEffector.idl
# generated code does not contain a copyright notice


# Import statements for member types

import builtins  # noqa: E402, I100

import math  # noqa: E402, I100

import rosidl_parser.definition  # noqa: E402, I100


class Metaclass_MoveEndEffector_Goal(type):
    """Metaclass of message 'MoveEndEffector_Goal'."""

    _CREATE_ROS_MESSAGE = None
    _CONVERT_FROM_PY = None
    _CONVERT_TO_PY = None
    _DESTROY_ROS_MESSAGE = None
    _TYPE_SUPPORT = None

    __constants = {
    }

    @classmethod
    def __import_type_support__(cls):
        try:
            from rosidl_generator_py import import_type_support
            module = import_type_support('a1z_msgs')
        except ImportError:
            import logging
            import traceback
            logger = logging.getLogger(
                'a1z_msgs.action.MoveEndEffector_Goal')
            logger.debug(
                'Failed to import needed modules for type support:\n' +
                traceback.format_exc())
        else:
            cls._CREATE_ROS_MESSAGE = module.create_ros_message_msg__action__move_end_effector__goal
            cls._CONVERT_FROM_PY = module.convert_from_py_msg__action__move_end_effector__goal
            cls._CONVERT_TO_PY = module.convert_to_py_msg__action__move_end_effector__goal
            cls._TYPE_SUPPORT = module.type_support_msg__action__move_end_effector__goal
            cls._DESTROY_ROS_MESSAGE = module.destroy_ros_message_msg__action__move_end_effector__goal

            from geometry_msgs.msg import PoseStamped
            if PoseStamped.__class__._TYPE_SUPPORT is None:
                PoseStamped.__class__.__import_type_support__()

    @classmethod
    def __prepare__(cls, name, bases, **kwargs):
        # list constant names here so that they appear in the help text of
        # the message class under "Data and other attributes defined here:"
        # as well as populate each message instance
        return {
        }


class MoveEndEffector_Goal(metaclass=Metaclass_MoveEndEffector_Goal):
    """Message class 'MoveEndEffector_Goal'."""

    __slots__ = [
        '_goal_pose',
        '_end_effector_frame',
        '_command_gripper',
        '_gripper_opening',
        '_speed',
        '_position_tolerance_m',
        '_orientation_tolerance_rad',
        '_joint_margin_rad',
        '_max_joint_step_rad',
        '_min_target_z_m',
        '_max_target_z_m',
    ]

    _fields_and_field_types = {
        'goal_pose': 'geometry_msgs/PoseStamped',
        'end_effector_frame': 'string',
        'command_gripper': 'boolean',
        'gripper_opening': 'float',
        'speed': 'float',
        'position_tolerance_m': 'float',
        'orientation_tolerance_rad': 'float',
        'joint_margin_rad': 'float',
        'max_joint_step_rad': 'float',
        'min_target_z_m': 'float',
        'max_target_z_m': 'float',
    }

    SLOT_TYPES = (
        rosidl_parser.definition.NamespacedType(['geometry_msgs', 'msg'], 'PoseStamped'),  # noqa: E501
        rosidl_parser.definition.UnboundedString(),  # noqa: E501
        rosidl_parser.definition.BasicType('boolean'),  # noqa: E501
        rosidl_parser.definition.BasicType('float'),  # noqa: E501
        rosidl_parser.definition.BasicType('float'),  # noqa: E501
        rosidl_parser.definition.BasicType('float'),  # noqa: E501
        rosidl_parser.definition.BasicType('float'),  # noqa: E501
        rosidl_parser.definition.BasicType('float'),  # noqa: E501
        rosidl_parser.definition.BasicType('float'),  # noqa: E501
        rosidl_parser.definition.BasicType('float'),  # noqa: E501
        rosidl_parser.definition.BasicType('float'),  # noqa: E501
    )

    def __init__(self, **kwargs):
        assert all('_' + key in self.__slots__ for key in kwargs.keys()), \
            'Invalid arguments passed to constructor: %s' % \
            ', '.join(sorted(k for k in kwargs.keys() if '_' + k not in self.__slots__))
        from geometry_msgs.msg import PoseStamped
        self.goal_pose = kwargs.get('goal_pose', PoseStamped())
        self.end_effector_frame = kwargs.get('end_effector_frame', str())
        self.command_gripper = kwargs.get('command_gripper', bool())
        self.gripper_opening = kwargs.get('gripper_opening', float())
        self.speed = kwargs.get('speed', float())
        self.position_tolerance_m = kwargs.get('position_tolerance_m', float())
        self.orientation_tolerance_rad = kwargs.get('orientation_tolerance_rad', float())
        self.joint_margin_rad = kwargs.get('joint_margin_rad', float())
        self.max_joint_step_rad = kwargs.get('max_joint_step_rad', float())
        self.min_target_z_m = kwargs.get('min_target_z_m', float())
        self.max_target_z_m = kwargs.get('max_target_z_m', float())

    def __repr__(self):
        typename = self.__class__.__module__.split('.')
        typename.pop()
        typename.append(self.__class__.__name__)
        args = []
        for s, t in zip(self.__slots__, self.SLOT_TYPES):
            field = getattr(self, s)
            fieldstr = repr(field)
            # We use Python array type for fields that can be directly stored
            # in them, and "normal" sequences for everything else.  If it is
            # a type that we store in an array, strip off the 'array' portion.
            if (
                isinstance(t, rosidl_parser.definition.AbstractSequence) and
                isinstance(t.value_type, rosidl_parser.definition.BasicType) and
                t.value_type.typename in ['float', 'double', 'int8', 'uint8', 'int16', 'uint16', 'int32', 'uint32', 'int64', 'uint64']
            ):
                if len(field) == 0:
                    fieldstr = '[]'
                else:
                    assert fieldstr.startswith('array(')
                    prefix = "array('X', "
                    suffix = ')'
                    fieldstr = fieldstr[len(prefix):-len(suffix)]
            args.append(s[1:] + '=' + fieldstr)
        return '%s(%s)' % ('.'.join(typename), ', '.join(args))

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        if self.goal_pose != other.goal_pose:
            return False
        if self.end_effector_frame != other.end_effector_frame:
            return False
        if self.command_gripper != other.command_gripper:
            return False
        if self.gripper_opening != other.gripper_opening:
            return False
        if self.speed != other.speed:
            return False
        if self.position_tolerance_m != other.position_tolerance_m:
            return False
        if self.orientation_tolerance_rad != other.orientation_tolerance_rad:
            return False
        if self.joint_margin_rad != other.joint_margin_rad:
            return False
        if self.max_joint_step_rad != other.max_joint_step_rad:
            return False
        if self.min_target_z_m != other.min_target_z_m:
            return False
        if self.max_target_z_m != other.max_target_z_m:
            return False
        return True

    @classmethod
    def get_fields_and_field_types(cls):
        from copy import copy
        return copy(cls._fields_and_field_types)

    @builtins.property
    def goal_pose(self):
        """Message field 'goal_pose'."""
        return self._goal_pose

    @goal_pose.setter
    def goal_pose(self, value):
        if __debug__:
            from geometry_msgs.msg import PoseStamped
            assert \
                isinstance(value, PoseStamped), \
                "The 'goal_pose' field must be a sub message of type 'PoseStamped'"
        self._goal_pose = value

    @builtins.property
    def end_effector_frame(self):
        """Message field 'end_effector_frame'."""
        return self._end_effector_frame

    @end_effector_frame.setter
    def end_effector_frame(self, value):
        if __debug__:
            assert \
                isinstance(value, str), \
                "The 'end_effector_frame' field must be of type 'str'"
        self._end_effector_frame = value

    @builtins.property
    def command_gripper(self):
        """Message field 'command_gripper'."""
        return self._command_gripper

    @command_gripper.setter
    def command_gripper(self, value):
        if __debug__:
            assert \
                isinstance(value, bool), \
                "The 'command_gripper' field must be of type 'bool'"
        self._command_gripper = value

    @builtins.property
    def gripper_opening(self):
        """Message field 'gripper_opening'."""
        return self._gripper_opening

    @gripper_opening.setter
    def gripper_opening(self, value):
        if __debug__:
            assert \
                isinstance(value, float), \
                "The 'gripper_opening' field must be of type 'float'"
            assert not (value < -3.402823466e+38 or value > 3.402823466e+38) or math.isinf(value), \
                "The 'gripper_opening' field must be a float in [-3.402823466e+38, 3.402823466e+38]"
        self._gripper_opening = value

    @builtins.property
    def speed(self):
        """Message field 'speed'."""
        return self._speed

    @speed.setter
    def speed(self, value):
        if __debug__:
            assert \
                isinstance(value, float), \
                "The 'speed' field must be of type 'float'"
            assert not (value < -3.402823466e+38 or value > 3.402823466e+38) or math.isinf(value), \
                "The 'speed' field must be a float in [-3.402823466e+38, 3.402823466e+38]"
        self._speed = value

    @builtins.property
    def position_tolerance_m(self):
        """Message field 'position_tolerance_m'."""
        return self._position_tolerance_m

    @position_tolerance_m.setter
    def position_tolerance_m(self, value):
        if __debug__:
            assert \
                isinstance(value, float), \
                "The 'position_tolerance_m' field must be of type 'float'"
            assert not (value < -3.402823466e+38 or value > 3.402823466e+38) or math.isinf(value), \
                "The 'position_tolerance_m' field must be a float in [-3.402823466e+38, 3.402823466e+38]"
        self._position_tolerance_m = value

    @builtins.property
    def orientation_tolerance_rad(self):
        """Message field 'orientation_tolerance_rad'."""
        return self._orientation_tolerance_rad

    @orientation_tolerance_rad.setter
    def orientation_tolerance_rad(self, value):
        if __debug__:
            assert \
                isinstance(value, float), \
                "The 'orientation_tolerance_rad' field must be of type 'float'"
            assert not (value < -3.402823466e+38 or value > 3.402823466e+38) or math.isinf(value), \
                "The 'orientation_tolerance_rad' field must be a float in [-3.402823466e+38, 3.402823466e+38]"
        self._orientation_tolerance_rad = value

    @builtins.property
    def joint_margin_rad(self):
        """Message field 'joint_margin_rad'."""
        return self._joint_margin_rad

    @joint_margin_rad.setter
    def joint_margin_rad(self, value):
        if __debug__:
            assert \
                isinstance(value, float), \
                "The 'joint_margin_rad' field must be of type 'float'"
            assert not (value < -3.402823466e+38 or value > 3.402823466e+38) or math.isinf(value), \
                "The 'joint_margin_rad' field must be a float in [-3.402823466e+38, 3.402823466e+38]"
        self._joint_margin_rad = value

    @builtins.property
    def max_joint_step_rad(self):
        """Message field 'max_joint_step_rad'."""
        return self._max_joint_step_rad

    @max_joint_step_rad.setter
    def max_joint_step_rad(self, value):
        if __debug__:
            assert \
                isinstance(value, float), \
                "The 'max_joint_step_rad' field must be of type 'float'"
            assert not (value < -3.402823466e+38 or value > 3.402823466e+38) or math.isinf(value), \
                "The 'max_joint_step_rad' field must be a float in [-3.402823466e+38, 3.402823466e+38]"
        self._max_joint_step_rad = value

    @builtins.property
    def min_target_z_m(self):
        """Message field 'min_target_z_m'."""
        return self._min_target_z_m

    @min_target_z_m.setter
    def min_target_z_m(self, value):
        if __debug__:
            assert \
                isinstance(value, float), \
                "The 'min_target_z_m' field must be of type 'float'"
            assert not (value < -3.402823466e+38 or value > 3.402823466e+38) or math.isinf(value), \
                "The 'min_target_z_m' field must be a float in [-3.402823466e+38, 3.402823466e+38]"
        self._min_target_z_m = value

    @builtins.property
    def max_target_z_m(self):
        """Message field 'max_target_z_m'."""
        return self._max_target_z_m

    @max_target_z_m.setter
    def max_target_z_m(self, value):
        if __debug__:
            assert \
                isinstance(value, float), \
                "The 'max_target_z_m' field must be of type 'float'"
            assert not (value < -3.402823466e+38 or value > 3.402823466e+38) or math.isinf(value), \
                "The 'max_target_z_m' field must be a float in [-3.402823466e+38, 3.402823466e+38]"
        self._max_target_z_m = value


# Import statements for member types

# Member 'final_joint_positions_rad'
import array  # noqa: E402, I100

# already imported above
# import builtins

# already imported above
# import math

# already imported above
# import rosidl_parser.definition


class Metaclass_MoveEndEffector_Result(type):
    """Metaclass of message 'MoveEndEffector_Result'."""

    _CREATE_ROS_MESSAGE = None
    _CONVERT_FROM_PY = None
    _CONVERT_TO_PY = None
    _DESTROY_ROS_MESSAGE = None
    _TYPE_SUPPORT = None

    __constants = {
    }

    @classmethod
    def __import_type_support__(cls):
        try:
            from rosidl_generator_py import import_type_support
            module = import_type_support('a1z_msgs')
        except ImportError:
            import logging
            import traceback
            logger = logging.getLogger(
                'a1z_msgs.action.MoveEndEffector_Result')
            logger.debug(
                'Failed to import needed modules for type support:\n' +
                traceback.format_exc())
        else:
            cls._CREATE_ROS_MESSAGE = module.create_ros_message_msg__action__move_end_effector__result
            cls._CONVERT_FROM_PY = module.convert_from_py_msg__action__move_end_effector__result
            cls._CONVERT_TO_PY = module.convert_to_py_msg__action__move_end_effector__result
            cls._TYPE_SUPPORT = module.type_support_msg__action__move_end_effector__result
            cls._DESTROY_ROS_MESSAGE = module.destroy_ros_message_msg__action__move_end_effector__result

            from geometry_msgs.msg import PoseStamped
            if PoseStamped.__class__._TYPE_SUPPORT is None:
                PoseStamped.__class__.__import_type_support__()

    @classmethod
    def __prepare__(cls, name, bases, **kwargs):
        # list constant names here so that they appear in the help text of
        # the message class under "Data and other attributes defined here:"
        # as well as populate each message instance
        return {
        }


class MoveEndEffector_Result(metaclass=Metaclass_MoveEndEffector_Result):
    """Message class 'MoveEndEffector_Result'."""

    __slots__ = [
        '_success',
        '_status',
        '_failure_reason',
        '_final_joint_positions_rad',
        '_final_pose',
        '_final_gripper_opening',
        '_ik_converged',
        '_position_error_m',
        '_orientation_error_rad',
    ]

    _fields_and_field_types = {
        'success': 'boolean',
        'status': 'string',
        'failure_reason': 'string',
        'final_joint_positions_rad': 'sequence<double>',
        'final_pose': 'geometry_msgs/PoseStamped',
        'final_gripper_opening': 'float',
        'ik_converged': 'boolean',
        'position_error_m': 'float',
        'orientation_error_rad': 'float',
    }

    SLOT_TYPES = (
        rosidl_parser.definition.BasicType('boolean'),  # noqa: E501
        rosidl_parser.definition.UnboundedString(),  # noqa: E501
        rosidl_parser.definition.UnboundedString(),  # noqa: E501
        rosidl_parser.definition.UnboundedSequence(rosidl_parser.definition.BasicType('double')),  # noqa: E501
        rosidl_parser.definition.NamespacedType(['geometry_msgs', 'msg'], 'PoseStamped'),  # noqa: E501
        rosidl_parser.definition.BasicType('float'),  # noqa: E501
        rosidl_parser.definition.BasicType('boolean'),  # noqa: E501
        rosidl_parser.definition.BasicType('float'),  # noqa: E501
        rosidl_parser.definition.BasicType('float'),  # noqa: E501
    )

    def __init__(self, **kwargs):
        assert all('_' + key in self.__slots__ for key in kwargs.keys()), \
            'Invalid arguments passed to constructor: %s' % \
            ', '.join(sorted(k for k in kwargs.keys() if '_' + k not in self.__slots__))
        self.success = kwargs.get('success', bool())
        self.status = kwargs.get('status', str())
        self.failure_reason = kwargs.get('failure_reason', str())
        self.final_joint_positions_rad = array.array('d', kwargs.get('final_joint_positions_rad', []))
        from geometry_msgs.msg import PoseStamped
        self.final_pose = kwargs.get('final_pose', PoseStamped())
        self.final_gripper_opening = kwargs.get('final_gripper_opening', float())
        self.ik_converged = kwargs.get('ik_converged', bool())
        self.position_error_m = kwargs.get('position_error_m', float())
        self.orientation_error_rad = kwargs.get('orientation_error_rad', float())

    def __repr__(self):
        typename = self.__class__.__module__.split('.')
        typename.pop()
        typename.append(self.__class__.__name__)
        args = []
        for s, t in zip(self.__slots__, self.SLOT_TYPES):
            field = getattr(self, s)
            fieldstr = repr(field)
            # We use Python array type for fields that can be directly stored
            # in them, and "normal" sequences for everything else.  If it is
            # a type that we store in an array, strip off the 'array' portion.
            if (
                isinstance(t, rosidl_parser.definition.AbstractSequence) and
                isinstance(t.value_type, rosidl_parser.definition.BasicType) and
                t.value_type.typename in ['float', 'double', 'int8', 'uint8', 'int16', 'uint16', 'int32', 'uint32', 'int64', 'uint64']
            ):
                if len(field) == 0:
                    fieldstr = '[]'
                else:
                    assert fieldstr.startswith('array(')
                    prefix = "array('X', "
                    suffix = ')'
                    fieldstr = fieldstr[len(prefix):-len(suffix)]
            args.append(s[1:] + '=' + fieldstr)
        return '%s(%s)' % ('.'.join(typename), ', '.join(args))

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        if self.success != other.success:
            return False
        if self.status != other.status:
            return False
        if self.failure_reason != other.failure_reason:
            return False
        if self.final_joint_positions_rad != other.final_joint_positions_rad:
            return False
        if self.final_pose != other.final_pose:
            return False
        if self.final_gripper_opening != other.final_gripper_opening:
            return False
        if self.ik_converged != other.ik_converged:
            return False
        if self.position_error_m != other.position_error_m:
            return False
        if self.orientation_error_rad != other.orientation_error_rad:
            return False
        return True

    @classmethod
    def get_fields_and_field_types(cls):
        from copy import copy
        return copy(cls._fields_and_field_types)

    @builtins.property
    def success(self):
        """Message field 'success'."""
        return self._success

    @success.setter
    def success(self, value):
        if __debug__:
            assert \
                isinstance(value, bool), \
                "The 'success' field must be of type 'bool'"
        self._success = value

    @builtins.property
    def status(self):
        """Message field 'status'."""
        return self._status

    @status.setter
    def status(self, value):
        if __debug__:
            assert \
                isinstance(value, str), \
                "The 'status' field must be of type 'str'"
        self._status = value

    @builtins.property
    def failure_reason(self):
        """Message field 'failure_reason'."""
        return self._failure_reason

    @failure_reason.setter
    def failure_reason(self, value):
        if __debug__:
            assert \
                isinstance(value, str), \
                "The 'failure_reason' field must be of type 'str'"
        self._failure_reason = value

    @builtins.property
    def final_joint_positions_rad(self):
        """Message field 'final_joint_positions_rad'."""
        return self._final_joint_positions_rad

    @final_joint_positions_rad.setter
    def final_joint_positions_rad(self, value):
        if isinstance(value, array.array):
            assert value.typecode == 'd', \
                "The 'final_joint_positions_rad' array.array() must have the type code of 'd'"
            self._final_joint_positions_rad = value
            return
        if __debug__:
            from collections.abc import Sequence
            from collections.abc import Set
            from collections import UserList
            from collections import UserString
            assert \
                ((isinstance(value, Sequence) or
                  isinstance(value, Set) or
                  isinstance(value, UserList)) and
                 not isinstance(value, str) and
                 not isinstance(value, UserString) and
                 all(isinstance(v, float) for v in value) and
                 all(not (val < -1.7976931348623157e+308 or val > 1.7976931348623157e+308) or math.isinf(val) for val in value)), \
                "The 'final_joint_positions_rad' field must be a set or sequence and each value of type 'float' and each double in [-179769313486231570814527423731704356798070567525844996598917476803157260780028538760589558632766878171540458953514382464234321326889464182768467546703537516986049910576551282076245490090389328944075868508455133942304583236903222948165808559332123348274797826204144723168738177180919299881250404026184124858368.000000, 179769313486231570814527423731704356798070567525844996598917476803157260780028538760589558632766878171540458953514382464234321326889464182768467546703537516986049910576551282076245490090389328944075868508455133942304583236903222948165808559332123348274797826204144723168738177180919299881250404026184124858368.000000]"
        self._final_joint_positions_rad = array.array('d', value)

    @builtins.property
    def final_pose(self):
        """Message field 'final_pose'."""
        return self._final_pose

    @final_pose.setter
    def final_pose(self, value):
        if __debug__:
            from geometry_msgs.msg import PoseStamped
            assert \
                isinstance(value, PoseStamped), \
                "The 'final_pose' field must be a sub message of type 'PoseStamped'"
        self._final_pose = value

    @builtins.property
    def final_gripper_opening(self):
        """Message field 'final_gripper_opening'."""
        return self._final_gripper_opening

    @final_gripper_opening.setter
    def final_gripper_opening(self, value):
        if __debug__:
            assert \
                isinstance(value, float), \
                "The 'final_gripper_opening' field must be of type 'float'"
            assert not (value < -3.402823466e+38 or value > 3.402823466e+38) or math.isinf(value), \
                "The 'final_gripper_opening' field must be a float in [-3.402823466e+38, 3.402823466e+38]"
        self._final_gripper_opening = value

    @builtins.property
    def ik_converged(self):
        """Message field 'ik_converged'."""
        return self._ik_converged

    @ik_converged.setter
    def ik_converged(self, value):
        if __debug__:
            assert \
                isinstance(value, bool), \
                "The 'ik_converged' field must be of type 'bool'"
        self._ik_converged = value

    @builtins.property
    def position_error_m(self):
        """Message field 'position_error_m'."""
        return self._position_error_m

    @position_error_m.setter
    def position_error_m(self, value):
        if __debug__:
            assert \
                isinstance(value, float), \
                "The 'position_error_m' field must be of type 'float'"
            assert not (value < -3.402823466e+38 or value > 3.402823466e+38) or math.isinf(value), \
                "The 'position_error_m' field must be a float in [-3.402823466e+38, 3.402823466e+38]"
        self._position_error_m = value

    @builtins.property
    def orientation_error_rad(self):
        """Message field 'orientation_error_rad'."""
        return self._orientation_error_rad

    @orientation_error_rad.setter
    def orientation_error_rad(self, value):
        if __debug__:
            assert \
                isinstance(value, float), \
                "The 'orientation_error_rad' field must be of type 'float'"
            assert not (value < -3.402823466e+38 or value > 3.402823466e+38) or math.isinf(value), \
                "The 'orientation_error_rad' field must be a float in [-3.402823466e+38, 3.402823466e+38]"
        self._orientation_error_rad = value


# Import statements for member types

# already imported above
# import builtins

# already imported above
# import rosidl_parser.definition


class Metaclass_MoveEndEffector_Feedback(type):
    """Metaclass of message 'MoveEndEffector_Feedback'."""

    _CREATE_ROS_MESSAGE = None
    _CONVERT_FROM_PY = None
    _CONVERT_TO_PY = None
    _DESTROY_ROS_MESSAGE = None
    _TYPE_SUPPORT = None

    __constants = {
    }

    @classmethod
    def __import_type_support__(cls):
        try:
            from rosidl_generator_py import import_type_support
            module = import_type_support('a1z_msgs')
        except ImportError:
            import logging
            import traceback
            logger = logging.getLogger(
                'a1z_msgs.action.MoveEndEffector_Feedback')
            logger.debug(
                'Failed to import needed modules for type support:\n' +
                traceback.format_exc())
        else:
            cls._CREATE_ROS_MESSAGE = module.create_ros_message_msg__action__move_end_effector__feedback
            cls._CONVERT_FROM_PY = module.convert_from_py_msg__action__move_end_effector__feedback
            cls._CONVERT_TO_PY = module.convert_to_py_msg__action__move_end_effector__feedback
            cls._TYPE_SUPPORT = module.type_support_msg__action__move_end_effector__feedback
            cls._DESTROY_ROS_MESSAGE = module.destroy_ros_message_msg__action__move_end_effector__feedback

    @classmethod
    def __prepare__(cls, name, bases, **kwargs):
        # list constant names here so that they appear in the help text of
        # the message class under "Data and other attributes defined here:"
        # as well as populate each message instance
        return {
        }


class MoveEndEffector_Feedback(metaclass=Metaclass_MoveEndEffector_Feedback):
    """Message class 'MoveEndEffector_Feedback'."""

    __slots__ = [
        '_stage',
        '_message',
    ]

    _fields_and_field_types = {
        'stage': 'string',
        'message': 'string',
    }

    SLOT_TYPES = (
        rosidl_parser.definition.UnboundedString(),  # noqa: E501
        rosidl_parser.definition.UnboundedString(),  # noqa: E501
    )

    def __init__(self, **kwargs):
        assert all('_' + key in self.__slots__ for key in kwargs.keys()), \
            'Invalid arguments passed to constructor: %s' % \
            ', '.join(sorted(k for k in kwargs.keys() if '_' + k not in self.__slots__))
        self.stage = kwargs.get('stage', str())
        self.message = kwargs.get('message', str())

    def __repr__(self):
        typename = self.__class__.__module__.split('.')
        typename.pop()
        typename.append(self.__class__.__name__)
        args = []
        for s, t in zip(self.__slots__, self.SLOT_TYPES):
            field = getattr(self, s)
            fieldstr = repr(field)
            # We use Python array type for fields that can be directly stored
            # in them, and "normal" sequences for everything else.  If it is
            # a type that we store in an array, strip off the 'array' portion.
            if (
                isinstance(t, rosidl_parser.definition.AbstractSequence) and
                isinstance(t.value_type, rosidl_parser.definition.BasicType) and
                t.value_type.typename in ['float', 'double', 'int8', 'uint8', 'int16', 'uint16', 'int32', 'uint32', 'int64', 'uint64']
            ):
                if len(field) == 0:
                    fieldstr = '[]'
                else:
                    assert fieldstr.startswith('array(')
                    prefix = "array('X', "
                    suffix = ')'
                    fieldstr = fieldstr[len(prefix):-len(suffix)]
            args.append(s[1:] + '=' + fieldstr)
        return '%s(%s)' % ('.'.join(typename), ', '.join(args))

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        if self.stage != other.stage:
            return False
        if self.message != other.message:
            return False
        return True

    @classmethod
    def get_fields_and_field_types(cls):
        from copy import copy
        return copy(cls._fields_and_field_types)

    @builtins.property
    def stage(self):
        """Message field 'stage'."""
        return self._stage

    @stage.setter
    def stage(self, value):
        if __debug__:
            assert \
                isinstance(value, str), \
                "The 'stage' field must be of type 'str'"
        self._stage = value

    @builtins.property
    def message(self):
        """Message field 'message'."""
        return self._message

    @message.setter
    def message(self, value):
        if __debug__:
            assert \
                isinstance(value, str), \
                "The 'message' field must be of type 'str'"
        self._message = value


# Import statements for member types

# already imported above
# import builtins

# already imported above
# import rosidl_parser.definition


class Metaclass_MoveEndEffector_SendGoal_Request(type):
    """Metaclass of message 'MoveEndEffector_SendGoal_Request'."""

    _CREATE_ROS_MESSAGE = None
    _CONVERT_FROM_PY = None
    _CONVERT_TO_PY = None
    _DESTROY_ROS_MESSAGE = None
    _TYPE_SUPPORT = None

    __constants = {
    }

    @classmethod
    def __import_type_support__(cls):
        try:
            from rosidl_generator_py import import_type_support
            module = import_type_support('a1z_msgs')
        except ImportError:
            import logging
            import traceback
            logger = logging.getLogger(
                'a1z_msgs.action.MoveEndEffector_SendGoal_Request')
            logger.debug(
                'Failed to import needed modules for type support:\n' +
                traceback.format_exc())
        else:
            cls._CREATE_ROS_MESSAGE = module.create_ros_message_msg__action__move_end_effector__send_goal__request
            cls._CONVERT_FROM_PY = module.convert_from_py_msg__action__move_end_effector__send_goal__request
            cls._CONVERT_TO_PY = module.convert_to_py_msg__action__move_end_effector__send_goal__request
            cls._TYPE_SUPPORT = module.type_support_msg__action__move_end_effector__send_goal__request
            cls._DESTROY_ROS_MESSAGE = module.destroy_ros_message_msg__action__move_end_effector__send_goal__request

            from a1z_msgs.action import MoveEndEffector
            if MoveEndEffector.Goal.__class__._TYPE_SUPPORT is None:
                MoveEndEffector.Goal.__class__.__import_type_support__()

            from unique_identifier_msgs.msg import UUID
            if UUID.__class__._TYPE_SUPPORT is None:
                UUID.__class__.__import_type_support__()

    @classmethod
    def __prepare__(cls, name, bases, **kwargs):
        # list constant names here so that they appear in the help text of
        # the message class under "Data and other attributes defined here:"
        # as well as populate each message instance
        return {
        }


class MoveEndEffector_SendGoal_Request(metaclass=Metaclass_MoveEndEffector_SendGoal_Request):
    """Message class 'MoveEndEffector_SendGoal_Request'."""

    __slots__ = [
        '_goal_id',
        '_goal',
    ]

    _fields_and_field_types = {
        'goal_id': 'unique_identifier_msgs/UUID',
        'goal': 'a1z_msgs/MoveEndEffector_Goal',
    }

    SLOT_TYPES = (
        rosidl_parser.definition.NamespacedType(['unique_identifier_msgs', 'msg'], 'UUID'),  # noqa: E501
        rosidl_parser.definition.NamespacedType(['a1z_msgs', 'action'], 'MoveEndEffector_Goal'),  # noqa: E501
    )

    def __init__(self, **kwargs):
        assert all('_' + key in self.__slots__ for key in kwargs.keys()), \
            'Invalid arguments passed to constructor: %s' % \
            ', '.join(sorted(k for k in kwargs.keys() if '_' + k not in self.__slots__))
        from unique_identifier_msgs.msg import UUID
        self.goal_id = kwargs.get('goal_id', UUID())
        from a1z_msgs.action._move_end_effector import MoveEndEffector_Goal
        self.goal = kwargs.get('goal', MoveEndEffector_Goal())

    def __repr__(self):
        typename = self.__class__.__module__.split('.')
        typename.pop()
        typename.append(self.__class__.__name__)
        args = []
        for s, t in zip(self.__slots__, self.SLOT_TYPES):
            field = getattr(self, s)
            fieldstr = repr(field)
            # We use Python array type for fields that can be directly stored
            # in them, and "normal" sequences for everything else.  If it is
            # a type that we store in an array, strip off the 'array' portion.
            if (
                isinstance(t, rosidl_parser.definition.AbstractSequence) and
                isinstance(t.value_type, rosidl_parser.definition.BasicType) and
                t.value_type.typename in ['float', 'double', 'int8', 'uint8', 'int16', 'uint16', 'int32', 'uint32', 'int64', 'uint64']
            ):
                if len(field) == 0:
                    fieldstr = '[]'
                else:
                    assert fieldstr.startswith('array(')
                    prefix = "array('X', "
                    suffix = ')'
                    fieldstr = fieldstr[len(prefix):-len(suffix)]
            args.append(s[1:] + '=' + fieldstr)
        return '%s(%s)' % ('.'.join(typename), ', '.join(args))

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        if self.goal_id != other.goal_id:
            return False
        if self.goal != other.goal:
            return False
        return True

    @classmethod
    def get_fields_and_field_types(cls):
        from copy import copy
        return copy(cls._fields_and_field_types)

    @builtins.property
    def goal_id(self):
        """Message field 'goal_id'."""
        return self._goal_id

    @goal_id.setter
    def goal_id(self, value):
        if __debug__:
            from unique_identifier_msgs.msg import UUID
            assert \
                isinstance(value, UUID), \
                "The 'goal_id' field must be a sub message of type 'UUID'"
        self._goal_id = value

    @builtins.property
    def goal(self):
        """Message field 'goal'."""
        return self._goal

    @goal.setter
    def goal(self, value):
        if __debug__:
            from a1z_msgs.action._move_end_effector import MoveEndEffector_Goal
            assert \
                isinstance(value, MoveEndEffector_Goal), \
                "The 'goal' field must be a sub message of type 'MoveEndEffector_Goal'"
        self._goal = value


# Import statements for member types

# already imported above
# import builtins

# already imported above
# import rosidl_parser.definition


class Metaclass_MoveEndEffector_SendGoal_Response(type):
    """Metaclass of message 'MoveEndEffector_SendGoal_Response'."""

    _CREATE_ROS_MESSAGE = None
    _CONVERT_FROM_PY = None
    _CONVERT_TO_PY = None
    _DESTROY_ROS_MESSAGE = None
    _TYPE_SUPPORT = None

    __constants = {
    }

    @classmethod
    def __import_type_support__(cls):
        try:
            from rosidl_generator_py import import_type_support
            module = import_type_support('a1z_msgs')
        except ImportError:
            import logging
            import traceback
            logger = logging.getLogger(
                'a1z_msgs.action.MoveEndEffector_SendGoal_Response')
            logger.debug(
                'Failed to import needed modules for type support:\n' +
                traceback.format_exc())
        else:
            cls._CREATE_ROS_MESSAGE = module.create_ros_message_msg__action__move_end_effector__send_goal__response
            cls._CONVERT_FROM_PY = module.convert_from_py_msg__action__move_end_effector__send_goal__response
            cls._CONVERT_TO_PY = module.convert_to_py_msg__action__move_end_effector__send_goal__response
            cls._TYPE_SUPPORT = module.type_support_msg__action__move_end_effector__send_goal__response
            cls._DESTROY_ROS_MESSAGE = module.destroy_ros_message_msg__action__move_end_effector__send_goal__response

            from builtin_interfaces.msg import Time
            if Time.__class__._TYPE_SUPPORT is None:
                Time.__class__.__import_type_support__()

    @classmethod
    def __prepare__(cls, name, bases, **kwargs):
        # list constant names here so that they appear in the help text of
        # the message class under "Data and other attributes defined here:"
        # as well as populate each message instance
        return {
        }


class MoveEndEffector_SendGoal_Response(metaclass=Metaclass_MoveEndEffector_SendGoal_Response):
    """Message class 'MoveEndEffector_SendGoal_Response'."""

    __slots__ = [
        '_accepted',
        '_stamp',
    ]

    _fields_and_field_types = {
        'accepted': 'boolean',
        'stamp': 'builtin_interfaces/Time',
    }

    SLOT_TYPES = (
        rosidl_parser.definition.BasicType('boolean'),  # noqa: E501
        rosidl_parser.definition.NamespacedType(['builtin_interfaces', 'msg'], 'Time'),  # noqa: E501
    )

    def __init__(self, **kwargs):
        assert all('_' + key in self.__slots__ for key in kwargs.keys()), \
            'Invalid arguments passed to constructor: %s' % \
            ', '.join(sorted(k for k in kwargs.keys() if '_' + k not in self.__slots__))
        self.accepted = kwargs.get('accepted', bool())
        from builtin_interfaces.msg import Time
        self.stamp = kwargs.get('stamp', Time())

    def __repr__(self):
        typename = self.__class__.__module__.split('.')
        typename.pop()
        typename.append(self.__class__.__name__)
        args = []
        for s, t in zip(self.__slots__, self.SLOT_TYPES):
            field = getattr(self, s)
            fieldstr = repr(field)
            # We use Python array type for fields that can be directly stored
            # in them, and "normal" sequences for everything else.  If it is
            # a type that we store in an array, strip off the 'array' portion.
            if (
                isinstance(t, rosidl_parser.definition.AbstractSequence) and
                isinstance(t.value_type, rosidl_parser.definition.BasicType) and
                t.value_type.typename in ['float', 'double', 'int8', 'uint8', 'int16', 'uint16', 'int32', 'uint32', 'int64', 'uint64']
            ):
                if len(field) == 0:
                    fieldstr = '[]'
                else:
                    assert fieldstr.startswith('array(')
                    prefix = "array('X', "
                    suffix = ')'
                    fieldstr = fieldstr[len(prefix):-len(suffix)]
            args.append(s[1:] + '=' + fieldstr)
        return '%s(%s)' % ('.'.join(typename), ', '.join(args))

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        if self.accepted != other.accepted:
            return False
        if self.stamp != other.stamp:
            return False
        return True

    @classmethod
    def get_fields_and_field_types(cls):
        from copy import copy
        return copy(cls._fields_and_field_types)

    @builtins.property
    def accepted(self):
        """Message field 'accepted'."""
        return self._accepted

    @accepted.setter
    def accepted(self, value):
        if __debug__:
            assert \
                isinstance(value, bool), \
                "The 'accepted' field must be of type 'bool'"
        self._accepted = value

    @builtins.property
    def stamp(self):
        """Message field 'stamp'."""
        return self._stamp

    @stamp.setter
    def stamp(self, value):
        if __debug__:
            from builtin_interfaces.msg import Time
            assert \
                isinstance(value, Time), \
                "The 'stamp' field must be a sub message of type 'Time'"
        self._stamp = value


class Metaclass_MoveEndEffector_SendGoal(type):
    """Metaclass of service 'MoveEndEffector_SendGoal'."""

    _TYPE_SUPPORT = None

    @classmethod
    def __import_type_support__(cls):
        try:
            from rosidl_generator_py import import_type_support
            module = import_type_support('a1z_msgs')
        except ImportError:
            import logging
            import traceback
            logger = logging.getLogger(
                'a1z_msgs.action.MoveEndEffector_SendGoal')
            logger.debug(
                'Failed to import needed modules for type support:\n' +
                traceback.format_exc())
        else:
            cls._TYPE_SUPPORT = module.type_support_srv__action__move_end_effector__send_goal

            from a1z_msgs.action import _move_end_effector
            if _move_end_effector.Metaclass_MoveEndEffector_SendGoal_Request._TYPE_SUPPORT is None:
                _move_end_effector.Metaclass_MoveEndEffector_SendGoal_Request.__import_type_support__()
            if _move_end_effector.Metaclass_MoveEndEffector_SendGoal_Response._TYPE_SUPPORT is None:
                _move_end_effector.Metaclass_MoveEndEffector_SendGoal_Response.__import_type_support__()


class MoveEndEffector_SendGoal(metaclass=Metaclass_MoveEndEffector_SendGoal):
    from a1z_msgs.action._move_end_effector import MoveEndEffector_SendGoal_Request as Request
    from a1z_msgs.action._move_end_effector import MoveEndEffector_SendGoal_Response as Response

    def __init__(self):
        raise NotImplementedError('Service classes can not be instantiated')


# Import statements for member types

# already imported above
# import builtins

# already imported above
# import rosidl_parser.definition


class Metaclass_MoveEndEffector_GetResult_Request(type):
    """Metaclass of message 'MoveEndEffector_GetResult_Request'."""

    _CREATE_ROS_MESSAGE = None
    _CONVERT_FROM_PY = None
    _CONVERT_TO_PY = None
    _DESTROY_ROS_MESSAGE = None
    _TYPE_SUPPORT = None

    __constants = {
    }

    @classmethod
    def __import_type_support__(cls):
        try:
            from rosidl_generator_py import import_type_support
            module = import_type_support('a1z_msgs')
        except ImportError:
            import logging
            import traceback
            logger = logging.getLogger(
                'a1z_msgs.action.MoveEndEffector_GetResult_Request')
            logger.debug(
                'Failed to import needed modules for type support:\n' +
                traceback.format_exc())
        else:
            cls._CREATE_ROS_MESSAGE = module.create_ros_message_msg__action__move_end_effector__get_result__request
            cls._CONVERT_FROM_PY = module.convert_from_py_msg__action__move_end_effector__get_result__request
            cls._CONVERT_TO_PY = module.convert_to_py_msg__action__move_end_effector__get_result__request
            cls._TYPE_SUPPORT = module.type_support_msg__action__move_end_effector__get_result__request
            cls._DESTROY_ROS_MESSAGE = module.destroy_ros_message_msg__action__move_end_effector__get_result__request

            from unique_identifier_msgs.msg import UUID
            if UUID.__class__._TYPE_SUPPORT is None:
                UUID.__class__.__import_type_support__()

    @classmethod
    def __prepare__(cls, name, bases, **kwargs):
        # list constant names here so that they appear in the help text of
        # the message class under "Data and other attributes defined here:"
        # as well as populate each message instance
        return {
        }


class MoveEndEffector_GetResult_Request(metaclass=Metaclass_MoveEndEffector_GetResult_Request):
    """Message class 'MoveEndEffector_GetResult_Request'."""

    __slots__ = [
        '_goal_id',
    ]

    _fields_and_field_types = {
        'goal_id': 'unique_identifier_msgs/UUID',
    }

    SLOT_TYPES = (
        rosidl_parser.definition.NamespacedType(['unique_identifier_msgs', 'msg'], 'UUID'),  # noqa: E501
    )

    def __init__(self, **kwargs):
        assert all('_' + key in self.__slots__ for key in kwargs.keys()), \
            'Invalid arguments passed to constructor: %s' % \
            ', '.join(sorted(k for k in kwargs.keys() if '_' + k not in self.__slots__))
        from unique_identifier_msgs.msg import UUID
        self.goal_id = kwargs.get('goal_id', UUID())

    def __repr__(self):
        typename = self.__class__.__module__.split('.')
        typename.pop()
        typename.append(self.__class__.__name__)
        args = []
        for s, t in zip(self.__slots__, self.SLOT_TYPES):
            field = getattr(self, s)
            fieldstr = repr(field)
            # We use Python array type for fields that can be directly stored
            # in them, and "normal" sequences for everything else.  If it is
            # a type that we store in an array, strip off the 'array' portion.
            if (
                isinstance(t, rosidl_parser.definition.AbstractSequence) and
                isinstance(t.value_type, rosidl_parser.definition.BasicType) and
                t.value_type.typename in ['float', 'double', 'int8', 'uint8', 'int16', 'uint16', 'int32', 'uint32', 'int64', 'uint64']
            ):
                if len(field) == 0:
                    fieldstr = '[]'
                else:
                    assert fieldstr.startswith('array(')
                    prefix = "array('X', "
                    suffix = ')'
                    fieldstr = fieldstr[len(prefix):-len(suffix)]
            args.append(s[1:] + '=' + fieldstr)
        return '%s(%s)' % ('.'.join(typename), ', '.join(args))

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        if self.goal_id != other.goal_id:
            return False
        return True

    @classmethod
    def get_fields_and_field_types(cls):
        from copy import copy
        return copy(cls._fields_and_field_types)

    @builtins.property
    def goal_id(self):
        """Message field 'goal_id'."""
        return self._goal_id

    @goal_id.setter
    def goal_id(self, value):
        if __debug__:
            from unique_identifier_msgs.msg import UUID
            assert \
                isinstance(value, UUID), \
                "The 'goal_id' field must be a sub message of type 'UUID'"
        self._goal_id = value


# Import statements for member types

# already imported above
# import builtins

# already imported above
# import rosidl_parser.definition


class Metaclass_MoveEndEffector_GetResult_Response(type):
    """Metaclass of message 'MoveEndEffector_GetResult_Response'."""

    _CREATE_ROS_MESSAGE = None
    _CONVERT_FROM_PY = None
    _CONVERT_TO_PY = None
    _DESTROY_ROS_MESSAGE = None
    _TYPE_SUPPORT = None

    __constants = {
    }

    @classmethod
    def __import_type_support__(cls):
        try:
            from rosidl_generator_py import import_type_support
            module = import_type_support('a1z_msgs')
        except ImportError:
            import logging
            import traceback
            logger = logging.getLogger(
                'a1z_msgs.action.MoveEndEffector_GetResult_Response')
            logger.debug(
                'Failed to import needed modules for type support:\n' +
                traceback.format_exc())
        else:
            cls._CREATE_ROS_MESSAGE = module.create_ros_message_msg__action__move_end_effector__get_result__response
            cls._CONVERT_FROM_PY = module.convert_from_py_msg__action__move_end_effector__get_result__response
            cls._CONVERT_TO_PY = module.convert_to_py_msg__action__move_end_effector__get_result__response
            cls._TYPE_SUPPORT = module.type_support_msg__action__move_end_effector__get_result__response
            cls._DESTROY_ROS_MESSAGE = module.destroy_ros_message_msg__action__move_end_effector__get_result__response

            from a1z_msgs.action import MoveEndEffector
            if MoveEndEffector.Result.__class__._TYPE_SUPPORT is None:
                MoveEndEffector.Result.__class__.__import_type_support__()

    @classmethod
    def __prepare__(cls, name, bases, **kwargs):
        # list constant names here so that they appear in the help text of
        # the message class under "Data and other attributes defined here:"
        # as well as populate each message instance
        return {
        }


class MoveEndEffector_GetResult_Response(metaclass=Metaclass_MoveEndEffector_GetResult_Response):
    """Message class 'MoveEndEffector_GetResult_Response'."""

    __slots__ = [
        '_status',
        '_result',
    ]

    _fields_and_field_types = {
        'status': 'int8',
        'result': 'a1z_msgs/MoveEndEffector_Result',
    }

    SLOT_TYPES = (
        rosidl_parser.definition.BasicType('int8'),  # noqa: E501
        rosidl_parser.definition.NamespacedType(['a1z_msgs', 'action'], 'MoveEndEffector_Result'),  # noqa: E501
    )

    def __init__(self, **kwargs):
        assert all('_' + key in self.__slots__ for key in kwargs.keys()), \
            'Invalid arguments passed to constructor: %s' % \
            ', '.join(sorted(k for k in kwargs.keys() if '_' + k not in self.__slots__))
        self.status = kwargs.get('status', int())
        from a1z_msgs.action._move_end_effector import MoveEndEffector_Result
        self.result = kwargs.get('result', MoveEndEffector_Result())

    def __repr__(self):
        typename = self.__class__.__module__.split('.')
        typename.pop()
        typename.append(self.__class__.__name__)
        args = []
        for s, t in zip(self.__slots__, self.SLOT_TYPES):
            field = getattr(self, s)
            fieldstr = repr(field)
            # We use Python array type for fields that can be directly stored
            # in them, and "normal" sequences for everything else.  If it is
            # a type that we store in an array, strip off the 'array' portion.
            if (
                isinstance(t, rosidl_parser.definition.AbstractSequence) and
                isinstance(t.value_type, rosidl_parser.definition.BasicType) and
                t.value_type.typename in ['float', 'double', 'int8', 'uint8', 'int16', 'uint16', 'int32', 'uint32', 'int64', 'uint64']
            ):
                if len(field) == 0:
                    fieldstr = '[]'
                else:
                    assert fieldstr.startswith('array(')
                    prefix = "array('X', "
                    suffix = ')'
                    fieldstr = fieldstr[len(prefix):-len(suffix)]
            args.append(s[1:] + '=' + fieldstr)
        return '%s(%s)' % ('.'.join(typename), ', '.join(args))

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        if self.status != other.status:
            return False
        if self.result != other.result:
            return False
        return True

    @classmethod
    def get_fields_and_field_types(cls):
        from copy import copy
        return copy(cls._fields_and_field_types)

    @builtins.property
    def status(self):
        """Message field 'status'."""
        return self._status

    @status.setter
    def status(self, value):
        if __debug__:
            assert \
                isinstance(value, int), \
                "The 'status' field must be of type 'int'"
            assert value >= -128 and value < 128, \
                "The 'status' field must be an integer in [-128, 127]"
        self._status = value

    @builtins.property
    def result(self):
        """Message field 'result'."""
        return self._result

    @result.setter
    def result(self, value):
        if __debug__:
            from a1z_msgs.action._move_end_effector import MoveEndEffector_Result
            assert \
                isinstance(value, MoveEndEffector_Result), \
                "The 'result' field must be a sub message of type 'MoveEndEffector_Result'"
        self._result = value


class Metaclass_MoveEndEffector_GetResult(type):
    """Metaclass of service 'MoveEndEffector_GetResult'."""

    _TYPE_SUPPORT = None

    @classmethod
    def __import_type_support__(cls):
        try:
            from rosidl_generator_py import import_type_support
            module = import_type_support('a1z_msgs')
        except ImportError:
            import logging
            import traceback
            logger = logging.getLogger(
                'a1z_msgs.action.MoveEndEffector_GetResult')
            logger.debug(
                'Failed to import needed modules for type support:\n' +
                traceback.format_exc())
        else:
            cls._TYPE_SUPPORT = module.type_support_srv__action__move_end_effector__get_result

            from a1z_msgs.action import _move_end_effector
            if _move_end_effector.Metaclass_MoveEndEffector_GetResult_Request._TYPE_SUPPORT is None:
                _move_end_effector.Metaclass_MoveEndEffector_GetResult_Request.__import_type_support__()
            if _move_end_effector.Metaclass_MoveEndEffector_GetResult_Response._TYPE_SUPPORT is None:
                _move_end_effector.Metaclass_MoveEndEffector_GetResult_Response.__import_type_support__()


class MoveEndEffector_GetResult(metaclass=Metaclass_MoveEndEffector_GetResult):
    from a1z_msgs.action._move_end_effector import MoveEndEffector_GetResult_Request as Request
    from a1z_msgs.action._move_end_effector import MoveEndEffector_GetResult_Response as Response

    def __init__(self):
        raise NotImplementedError('Service classes can not be instantiated')


# Import statements for member types

# already imported above
# import builtins

# already imported above
# import rosidl_parser.definition


class Metaclass_MoveEndEffector_FeedbackMessage(type):
    """Metaclass of message 'MoveEndEffector_FeedbackMessage'."""

    _CREATE_ROS_MESSAGE = None
    _CONVERT_FROM_PY = None
    _CONVERT_TO_PY = None
    _DESTROY_ROS_MESSAGE = None
    _TYPE_SUPPORT = None

    __constants = {
    }

    @classmethod
    def __import_type_support__(cls):
        try:
            from rosidl_generator_py import import_type_support
            module = import_type_support('a1z_msgs')
        except ImportError:
            import logging
            import traceback
            logger = logging.getLogger(
                'a1z_msgs.action.MoveEndEffector_FeedbackMessage')
            logger.debug(
                'Failed to import needed modules for type support:\n' +
                traceback.format_exc())
        else:
            cls._CREATE_ROS_MESSAGE = module.create_ros_message_msg__action__move_end_effector__feedback_message
            cls._CONVERT_FROM_PY = module.convert_from_py_msg__action__move_end_effector__feedback_message
            cls._CONVERT_TO_PY = module.convert_to_py_msg__action__move_end_effector__feedback_message
            cls._TYPE_SUPPORT = module.type_support_msg__action__move_end_effector__feedback_message
            cls._DESTROY_ROS_MESSAGE = module.destroy_ros_message_msg__action__move_end_effector__feedback_message

            from a1z_msgs.action import MoveEndEffector
            if MoveEndEffector.Feedback.__class__._TYPE_SUPPORT is None:
                MoveEndEffector.Feedback.__class__.__import_type_support__()

            from unique_identifier_msgs.msg import UUID
            if UUID.__class__._TYPE_SUPPORT is None:
                UUID.__class__.__import_type_support__()

    @classmethod
    def __prepare__(cls, name, bases, **kwargs):
        # list constant names here so that they appear in the help text of
        # the message class under "Data and other attributes defined here:"
        # as well as populate each message instance
        return {
        }


class MoveEndEffector_FeedbackMessage(metaclass=Metaclass_MoveEndEffector_FeedbackMessage):
    """Message class 'MoveEndEffector_FeedbackMessage'."""

    __slots__ = [
        '_goal_id',
        '_feedback',
    ]

    _fields_and_field_types = {
        'goal_id': 'unique_identifier_msgs/UUID',
        'feedback': 'a1z_msgs/MoveEndEffector_Feedback',
    }

    SLOT_TYPES = (
        rosidl_parser.definition.NamespacedType(['unique_identifier_msgs', 'msg'], 'UUID'),  # noqa: E501
        rosidl_parser.definition.NamespacedType(['a1z_msgs', 'action'], 'MoveEndEffector_Feedback'),  # noqa: E501
    )

    def __init__(self, **kwargs):
        assert all('_' + key in self.__slots__ for key in kwargs.keys()), \
            'Invalid arguments passed to constructor: %s' % \
            ', '.join(sorted(k for k in kwargs.keys() if '_' + k not in self.__slots__))
        from unique_identifier_msgs.msg import UUID
        self.goal_id = kwargs.get('goal_id', UUID())
        from a1z_msgs.action._move_end_effector import MoveEndEffector_Feedback
        self.feedback = kwargs.get('feedback', MoveEndEffector_Feedback())

    def __repr__(self):
        typename = self.__class__.__module__.split('.')
        typename.pop()
        typename.append(self.__class__.__name__)
        args = []
        for s, t in zip(self.__slots__, self.SLOT_TYPES):
            field = getattr(self, s)
            fieldstr = repr(field)
            # We use Python array type for fields that can be directly stored
            # in them, and "normal" sequences for everything else.  If it is
            # a type that we store in an array, strip off the 'array' portion.
            if (
                isinstance(t, rosidl_parser.definition.AbstractSequence) and
                isinstance(t.value_type, rosidl_parser.definition.BasicType) and
                t.value_type.typename in ['float', 'double', 'int8', 'uint8', 'int16', 'uint16', 'int32', 'uint32', 'int64', 'uint64']
            ):
                if len(field) == 0:
                    fieldstr = '[]'
                else:
                    assert fieldstr.startswith('array(')
                    prefix = "array('X', "
                    suffix = ')'
                    fieldstr = fieldstr[len(prefix):-len(suffix)]
            args.append(s[1:] + '=' + fieldstr)
        return '%s(%s)' % ('.'.join(typename), ', '.join(args))

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        if self.goal_id != other.goal_id:
            return False
        if self.feedback != other.feedback:
            return False
        return True

    @classmethod
    def get_fields_and_field_types(cls):
        from copy import copy
        return copy(cls._fields_and_field_types)

    @builtins.property
    def goal_id(self):
        """Message field 'goal_id'."""
        return self._goal_id

    @goal_id.setter
    def goal_id(self, value):
        if __debug__:
            from unique_identifier_msgs.msg import UUID
            assert \
                isinstance(value, UUID), \
                "The 'goal_id' field must be a sub message of type 'UUID'"
        self._goal_id = value

    @builtins.property
    def feedback(self):
        """Message field 'feedback'."""
        return self._feedback

    @feedback.setter
    def feedback(self, value):
        if __debug__:
            from a1z_msgs.action._move_end_effector import MoveEndEffector_Feedback
            assert \
                isinstance(value, MoveEndEffector_Feedback), \
                "The 'feedback' field must be a sub message of type 'MoveEndEffector_Feedback'"
        self._feedback = value


class Metaclass_MoveEndEffector(type):
    """Metaclass of action 'MoveEndEffector'."""

    _TYPE_SUPPORT = None

    @classmethod
    def __import_type_support__(cls):
        try:
            from rosidl_generator_py import import_type_support
            module = import_type_support('a1z_msgs')
        except ImportError:
            import logging
            import traceback
            logger = logging.getLogger(
                'a1z_msgs.action.MoveEndEffector')
            logger.debug(
                'Failed to import needed modules for type support:\n' +
                traceback.format_exc())
        else:
            cls._TYPE_SUPPORT = module.type_support_action__action__move_end_effector

            from action_msgs.msg import _goal_status_array
            if _goal_status_array.Metaclass_GoalStatusArray._TYPE_SUPPORT is None:
                _goal_status_array.Metaclass_GoalStatusArray.__import_type_support__()
            from action_msgs.srv import _cancel_goal
            if _cancel_goal.Metaclass_CancelGoal._TYPE_SUPPORT is None:
                _cancel_goal.Metaclass_CancelGoal.__import_type_support__()

            from a1z_msgs.action import _move_end_effector
            if _move_end_effector.Metaclass_MoveEndEffector_SendGoal._TYPE_SUPPORT is None:
                _move_end_effector.Metaclass_MoveEndEffector_SendGoal.__import_type_support__()
            if _move_end_effector.Metaclass_MoveEndEffector_GetResult._TYPE_SUPPORT is None:
                _move_end_effector.Metaclass_MoveEndEffector_GetResult.__import_type_support__()
            if _move_end_effector.Metaclass_MoveEndEffector_FeedbackMessage._TYPE_SUPPORT is None:
                _move_end_effector.Metaclass_MoveEndEffector_FeedbackMessage.__import_type_support__()


class MoveEndEffector(metaclass=Metaclass_MoveEndEffector):

    # The goal message defined in the action definition.
    from a1z_msgs.action._move_end_effector import MoveEndEffector_Goal as Goal
    # The result message defined in the action definition.
    from a1z_msgs.action._move_end_effector import MoveEndEffector_Result as Result
    # The feedback message defined in the action definition.
    from a1z_msgs.action._move_end_effector import MoveEndEffector_Feedback as Feedback

    class Impl:

        # The send_goal service using a wrapped version of the goal message as a request.
        from a1z_msgs.action._move_end_effector import MoveEndEffector_SendGoal as SendGoalService
        # The get_result service using a wrapped version of the result message as a response.
        from a1z_msgs.action._move_end_effector import MoveEndEffector_GetResult as GetResultService
        # The feedback message with generic fields which wraps the feedback message.
        from a1z_msgs.action._move_end_effector import MoveEndEffector_FeedbackMessage as FeedbackMessage

        # The generic service to cancel a goal.
        from action_msgs.srv._cancel_goal import CancelGoal as CancelGoalService
        # The generic message for get the status of a goal.
        from action_msgs.msg._goal_status_array import GoalStatusArray as GoalStatusMessage

    def __init__(self):
        raise NotImplementedError('Action classes can not be instantiated')
