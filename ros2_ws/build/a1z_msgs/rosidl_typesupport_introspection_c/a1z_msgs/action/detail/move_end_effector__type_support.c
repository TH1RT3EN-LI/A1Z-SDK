// generated from rosidl_typesupport_introspection_c/resource/idl__type_support.c.em
// with input from a1z_msgs:action/MoveEndEffector.idl
// generated code does not contain a copyright notice

#include <stddef.h>
#include "a1z_msgs/action/detail/move_end_effector__rosidl_typesupport_introspection_c.h"
#include "a1z_msgs/msg/rosidl_typesupport_introspection_c__visibility_control.h"
#include "rosidl_typesupport_introspection_c/field_types.h"
#include "rosidl_typesupport_introspection_c/identifier.h"
#include "rosidl_typesupport_introspection_c/message_introspection.h"
#include "a1z_msgs/action/detail/move_end_effector__functions.h"
#include "a1z_msgs/action/detail/move_end_effector__struct.h"


// Include directives for member types
// Member `goal_pose`
#include "geometry_msgs/msg/pose_stamped.h"
// Member `goal_pose`
#include "geometry_msgs/msg/detail/pose_stamped__rosidl_typesupport_introspection_c.h"
// Member `end_effector_frame`
#include "rosidl_runtime_c/string_functions.h"

#ifdef __cplusplus
extern "C"
{
#endif

void a1z_msgs__action__MoveEndEffector_Goal__rosidl_typesupport_introspection_c__MoveEndEffector_Goal_init_function(
  void * message_memory, enum rosidl_runtime_c__message_initialization _init)
{
  // TODO(karsten1987): initializers are not yet implemented for typesupport c
  // see https://github.com/ros2/ros2/issues/397
  (void) _init;
  a1z_msgs__action__MoveEndEffector_Goal__init(message_memory);
}

void a1z_msgs__action__MoveEndEffector_Goal__rosidl_typesupport_introspection_c__MoveEndEffector_Goal_fini_function(void * message_memory)
{
  a1z_msgs__action__MoveEndEffector_Goal__fini(message_memory);
}

static rosidl_typesupport_introspection_c__MessageMember a1z_msgs__action__MoveEndEffector_Goal__rosidl_typesupport_introspection_c__MoveEndEffector_Goal_message_member_array[11] = {
  {
    "goal_pose",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_MESSAGE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message (initialized later)
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(a1z_msgs__action__MoveEndEffector_Goal, goal_pose),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "end_effector_frame",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_STRING,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(a1z_msgs__action__MoveEndEffector_Goal, end_effector_frame),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "command_gripper",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_BOOLEAN,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(a1z_msgs__action__MoveEndEffector_Goal, command_gripper),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "gripper_opening",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_FLOAT,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(a1z_msgs__action__MoveEndEffector_Goal, gripper_opening),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "speed",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_FLOAT,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(a1z_msgs__action__MoveEndEffector_Goal, speed),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "position_tolerance_m",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_FLOAT,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(a1z_msgs__action__MoveEndEffector_Goal, position_tolerance_m),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "orientation_tolerance_rad",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_FLOAT,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(a1z_msgs__action__MoveEndEffector_Goal, orientation_tolerance_rad),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "joint_margin_rad",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_FLOAT,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(a1z_msgs__action__MoveEndEffector_Goal, joint_margin_rad),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "max_joint_step_rad",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_FLOAT,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(a1z_msgs__action__MoveEndEffector_Goal, max_joint_step_rad),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "min_target_z_m",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_FLOAT,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(a1z_msgs__action__MoveEndEffector_Goal, min_target_z_m),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "max_target_z_m",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_FLOAT,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(a1z_msgs__action__MoveEndEffector_Goal, max_target_z_m),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  }
};

static const rosidl_typesupport_introspection_c__MessageMembers a1z_msgs__action__MoveEndEffector_Goal__rosidl_typesupport_introspection_c__MoveEndEffector_Goal_message_members = {
  "a1z_msgs__action",  // message namespace
  "MoveEndEffector_Goal",  // message name
  11,  // number of fields
  sizeof(a1z_msgs__action__MoveEndEffector_Goal),
  a1z_msgs__action__MoveEndEffector_Goal__rosidl_typesupport_introspection_c__MoveEndEffector_Goal_message_member_array,  // message members
  a1z_msgs__action__MoveEndEffector_Goal__rosidl_typesupport_introspection_c__MoveEndEffector_Goal_init_function,  // function to initialize message memory (memory has to be allocated)
  a1z_msgs__action__MoveEndEffector_Goal__rosidl_typesupport_introspection_c__MoveEndEffector_Goal_fini_function  // function to terminate message instance (will not free memory)
};

// this is not const since it must be initialized on first access
// since C does not allow non-integral compile-time constants
static rosidl_message_type_support_t a1z_msgs__action__MoveEndEffector_Goal__rosidl_typesupport_introspection_c__MoveEndEffector_Goal_message_type_support_handle = {
  0,
  &a1z_msgs__action__MoveEndEffector_Goal__rosidl_typesupport_introspection_c__MoveEndEffector_Goal_message_members,
  get_message_typesupport_handle_function,
};

ROSIDL_TYPESUPPORT_INTROSPECTION_C_EXPORT_a1z_msgs
const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, a1z_msgs, action, MoveEndEffector_Goal)() {
  a1z_msgs__action__MoveEndEffector_Goal__rosidl_typesupport_introspection_c__MoveEndEffector_Goal_message_member_array[0].members_ =
    ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, geometry_msgs, msg, PoseStamped)();
  if (!a1z_msgs__action__MoveEndEffector_Goal__rosidl_typesupport_introspection_c__MoveEndEffector_Goal_message_type_support_handle.typesupport_identifier) {
    a1z_msgs__action__MoveEndEffector_Goal__rosidl_typesupport_introspection_c__MoveEndEffector_Goal_message_type_support_handle.typesupport_identifier =
      rosidl_typesupport_introspection_c__identifier;
  }
  return &a1z_msgs__action__MoveEndEffector_Goal__rosidl_typesupport_introspection_c__MoveEndEffector_Goal_message_type_support_handle;
}
#ifdef __cplusplus
}
#endif

// already included above
// #include <stddef.h>
// already included above
// #include "a1z_msgs/action/detail/move_end_effector__rosidl_typesupport_introspection_c.h"
// already included above
// #include "a1z_msgs/msg/rosidl_typesupport_introspection_c__visibility_control.h"
// already included above
// #include "rosidl_typesupport_introspection_c/field_types.h"
// already included above
// #include "rosidl_typesupport_introspection_c/identifier.h"
// already included above
// #include "rosidl_typesupport_introspection_c/message_introspection.h"
// already included above
// #include "a1z_msgs/action/detail/move_end_effector__functions.h"
// already included above
// #include "a1z_msgs/action/detail/move_end_effector__struct.h"


// Include directives for member types
// Member `status`
// Member `failure_reason`
// already included above
// #include "rosidl_runtime_c/string_functions.h"
// Member `final_joint_positions_rad`
#include "rosidl_runtime_c/primitives_sequence_functions.h"
// Member `final_pose`
// already included above
// #include "geometry_msgs/msg/pose_stamped.h"
// Member `final_pose`
// already included above
// #include "geometry_msgs/msg/detail/pose_stamped__rosidl_typesupport_introspection_c.h"

#ifdef __cplusplus
extern "C"
{
#endif

void a1z_msgs__action__MoveEndEffector_Result__rosidl_typesupport_introspection_c__MoveEndEffector_Result_init_function(
  void * message_memory, enum rosidl_runtime_c__message_initialization _init)
{
  // TODO(karsten1987): initializers are not yet implemented for typesupport c
  // see https://github.com/ros2/ros2/issues/397
  (void) _init;
  a1z_msgs__action__MoveEndEffector_Result__init(message_memory);
}

void a1z_msgs__action__MoveEndEffector_Result__rosidl_typesupport_introspection_c__MoveEndEffector_Result_fini_function(void * message_memory)
{
  a1z_msgs__action__MoveEndEffector_Result__fini(message_memory);
}

size_t a1z_msgs__action__MoveEndEffector_Result__rosidl_typesupport_introspection_c__size_function__MoveEndEffector_Result__final_joint_positions_rad(
  const void * untyped_member)
{
  const rosidl_runtime_c__double__Sequence * member =
    (const rosidl_runtime_c__double__Sequence *)(untyped_member);
  return member->size;
}

const void * a1z_msgs__action__MoveEndEffector_Result__rosidl_typesupport_introspection_c__get_const_function__MoveEndEffector_Result__final_joint_positions_rad(
  const void * untyped_member, size_t index)
{
  const rosidl_runtime_c__double__Sequence * member =
    (const rosidl_runtime_c__double__Sequence *)(untyped_member);
  return &member->data[index];
}

void * a1z_msgs__action__MoveEndEffector_Result__rosidl_typesupport_introspection_c__get_function__MoveEndEffector_Result__final_joint_positions_rad(
  void * untyped_member, size_t index)
{
  rosidl_runtime_c__double__Sequence * member =
    (rosidl_runtime_c__double__Sequence *)(untyped_member);
  return &member->data[index];
}

void a1z_msgs__action__MoveEndEffector_Result__rosidl_typesupport_introspection_c__fetch_function__MoveEndEffector_Result__final_joint_positions_rad(
  const void * untyped_member, size_t index, void * untyped_value)
{
  const double * item =
    ((const double *)
    a1z_msgs__action__MoveEndEffector_Result__rosidl_typesupport_introspection_c__get_const_function__MoveEndEffector_Result__final_joint_positions_rad(untyped_member, index));
  double * value =
    (double *)(untyped_value);
  *value = *item;
}

void a1z_msgs__action__MoveEndEffector_Result__rosidl_typesupport_introspection_c__assign_function__MoveEndEffector_Result__final_joint_positions_rad(
  void * untyped_member, size_t index, const void * untyped_value)
{
  double * item =
    ((double *)
    a1z_msgs__action__MoveEndEffector_Result__rosidl_typesupport_introspection_c__get_function__MoveEndEffector_Result__final_joint_positions_rad(untyped_member, index));
  const double * value =
    (const double *)(untyped_value);
  *item = *value;
}

bool a1z_msgs__action__MoveEndEffector_Result__rosidl_typesupport_introspection_c__resize_function__MoveEndEffector_Result__final_joint_positions_rad(
  void * untyped_member, size_t size)
{
  rosidl_runtime_c__double__Sequence * member =
    (rosidl_runtime_c__double__Sequence *)(untyped_member);
  rosidl_runtime_c__double__Sequence__fini(member);
  return rosidl_runtime_c__double__Sequence__init(member, size);
}

static rosidl_typesupport_introspection_c__MessageMember a1z_msgs__action__MoveEndEffector_Result__rosidl_typesupport_introspection_c__MoveEndEffector_Result_message_member_array[9] = {
  {
    "success",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_BOOLEAN,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(a1z_msgs__action__MoveEndEffector_Result, success),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "status",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_STRING,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(a1z_msgs__action__MoveEndEffector_Result, status),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "failure_reason",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_STRING,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(a1z_msgs__action__MoveEndEffector_Result, failure_reason),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "final_joint_positions_rad",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_DOUBLE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    true,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(a1z_msgs__action__MoveEndEffector_Result, final_joint_positions_rad),  // bytes offset in struct
    NULL,  // default value
    a1z_msgs__action__MoveEndEffector_Result__rosidl_typesupport_introspection_c__size_function__MoveEndEffector_Result__final_joint_positions_rad,  // size() function pointer
    a1z_msgs__action__MoveEndEffector_Result__rosidl_typesupport_introspection_c__get_const_function__MoveEndEffector_Result__final_joint_positions_rad,  // get_const(index) function pointer
    a1z_msgs__action__MoveEndEffector_Result__rosidl_typesupport_introspection_c__get_function__MoveEndEffector_Result__final_joint_positions_rad,  // get(index) function pointer
    a1z_msgs__action__MoveEndEffector_Result__rosidl_typesupport_introspection_c__fetch_function__MoveEndEffector_Result__final_joint_positions_rad,  // fetch(index, &value) function pointer
    a1z_msgs__action__MoveEndEffector_Result__rosidl_typesupport_introspection_c__assign_function__MoveEndEffector_Result__final_joint_positions_rad,  // assign(index, value) function pointer
    a1z_msgs__action__MoveEndEffector_Result__rosidl_typesupport_introspection_c__resize_function__MoveEndEffector_Result__final_joint_positions_rad  // resize(index) function pointer
  },
  {
    "final_pose",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_MESSAGE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message (initialized later)
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(a1z_msgs__action__MoveEndEffector_Result, final_pose),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "final_gripper_opening",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_FLOAT,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(a1z_msgs__action__MoveEndEffector_Result, final_gripper_opening),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "ik_converged",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_BOOLEAN,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(a1z_msgs__action__MoveEndEffector_Result, ik_converged),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "position_error_m",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_FLOAT,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(a1z_msgs__action__MoveEndEffector_Result, position_error_m),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "orientation_error_rad",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_FLOAT,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(a1z_msgs__action__MoveEndEffector_Result, orientation_error_rad),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  }
};

static const rosidl_typesupport_introspection_c__MessageMembers a1z_msgs__action__MoveEndEffector_Result__rosidl_typesupport_introspection_c__MoveEndEffector_Result_message_members = {
  "a1z_msgs__action",  // message namespace
  "MoveEndEffector_Result",  // message name
  9,  // number of fields
  sizeof(a1z_msgs__action__MoveEndEffector_Result),
  a1z_msgs__action__MoveEndEffector_Result__rosidl_typesupport_introspection_c__MoveEndEffector_Result_message_member_array,  // message members
  a1z_msgs__action__MoveEndEffector_Result__rosidl_typesupport_introspection_c__MoveEndEffector_Result_init_function,  // function to initialize message memory (memory has to be allocated)
  a1z_msgs__action__MoveEndEffector_Result__rosidl_typesupport_introspection_c__MoveEndEffector_Result_fini_function  // function to terminate message instance (will not free memory)
};

// this is not const since it must be initialized on first access
// since C does not allow non-integral compile-time constants
static rosidl_message_type_support_t a1z_msgs__action__MoveEndEffector_Result__rosidl_typesupport_introspection_c__MoveEndEffector_Result_message_type_support_handle = {
  0,
  &a1z_msgs__action__MoveEndEffector_Result__rosidl_typesupport_introspection_c__MoveEndEffector_Result_message_members,
  get_message_typesupport_handle_function,
};

ROSIDL_TYPESUPPORT_INTROSPECTION_C_EXPORT_a1z_msgs
const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, a1z_msgs, action, MoveEndEffector_Result)() {
  a1z_msgs__action__MoveEndEffector_Result__rosidl_typesupport_introspection_c__MoveEndEffector_Result_message_member_array[4].members_ =
    ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, geometry_msgs, msg, PoseStamped)();
  if (!a1z_msgs__action__MoveEndEffector_Result__rosidl_typesupport_introspection_c__MoveEndEffector_Result_message_type_support_handle.typesupport_identifier) {
    a1z_msgs__action__MoveEndEffector_Result__rosidl_typesupport_introspection_c__MoveEndEffector_Result_message_type_support_handle.typesupport_identifier =
      rosidl_typesupport_introspection_c__identifier;
  }
  return &a1z_msgs__action__MoveEndEffector_Result__rosidl_typesupport_introspection_c__MoveEndEffector_Result_message_type_support_handle;
}
#ifdef __cplusplus
}
#endif

// already included above
// #include <stddef.h>
// already included above
// #include "a1z_msgs/action/detail/move_end_effector__rosidl_typesupport_introspection_c.h"
// already included above
// #include "a1z_msgs/msg/rosidl_typesupport_introspection_c__visibility_control.h"
// already included above
// #include "rosidl_typesupport_introspection_c/field_types.h"
// already included above
// #include "rosidl_typesupport_introspection_c/identifier.h"
// already included above
// #include "rosidl_typesupport_introspection_c/message_introspection.h"
// already included above
// #include "a1z_msgs/action/detail/move_end_effector__functions.h"
// already included above
// #include "a1z_msgs/action/detail/move_end_effector__struct.h"


// Include directives for member types
// Member `stage`
// Member `message`
// already included above
// #include "rosidl_runtime_c/string_functions.h"

#ifdef __cplusplus
extern "C"
{
#endif

void a1z_msgs__action__MoveEndEffector_Feedback__rosidl_typesupport_introspection_c__MoveEndEffector_Feedback_init_function(
  void * message_memory, enum rosidl_runtime_c__message_initialization _init)
{
  // TODO(karsten1987): initializers are not yet implemented for typesupport c
  // see https://github.com/ros2/ros2/issues/397
  (void) _init;
  a1z_msgs__action__MoveEndEffector_Feedback__init(message_memory);
}

void a1z_msgs__action__MoveEndEffector_Feedback__rosidl_typesupport_introspection_c__MoveEndEffector_Feedback_fini_function(void * message_memory)
{
  a1z_msgs__action__MoveEndEffector_Feedback__fini(message_memory);
}

static rosidl_typesupport_introspection_c__MessageMember a1z_msgs__action__MoveEndEffector_Feedback__rosidl_typesupport_introspection_c__MoveEndEffector_Feedback_message_member_array[2] = {
  {
    "stage",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_STRING,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(a1z_msgs__action__MoveEndEffector_Feedback, stage),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "message",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_STRING,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(a1z_msgs__action__MoveEndEffector_Feedback, message),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  }
};

static const rosidl_typesupport_introspection_c__MessageMembers a1z_msgs__action__MoveEndEffector_Feedback__rosidl_typesupport_introspection_c__MoveEndEffector_Feedback_message_members = {
  "a1z_msgs__action",  // message namespace
  "MoveEndEffector_Feedback",  // message name
  2,  // number of fields
  sizeof(a1z_msgs__action__MoveEndEffector_Feedback),
  a1z_msgs__action__MoveEndEffector_Feedback__rosidl_typesupport_introspection_c__MoveEndEffector_Feedback_message_member_array,  // message members
  a1z_msgs__action__MoveEndEffector_Feedback__rosidl_typesupport_introspection_c__MoveEndEffector_Feedback_init_function,  // function to initialize message memory (memory has to be allocated)
  a1z_msgs__action__MoveEndEffector_Feedback__rosidl_typesupport_introspection_c__MoveEndEffector_Feedback_fini_function  // function to terminate message instance (will not free memory)
};

// this is not const since it must be initialized on first access
// since C does not allow non-integral compile-time constants
static rosidl_message_type_support_t a1z_msgs__action__MoveEndEffector_Feedback__rosidl_typesupport_introspection_c__MoveEndEffector_Feedback_message_type_support_handle = {
  0,
  &a1z_msgs__action__MoveEndEffector_Feedback__rosidl_typesupport_introspection_c__MoveEndEffector_Feedback_message_members,
  get_message_typesupport_handle_function,
};

ROSIDL_TYPESUPPORT_INTROSPECTION_C_EXPORT_a1z_msgs
const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, a1z_msgs, action, MoveEndEffector_Feedback)() {
  if (!a1z_msgs__action__MoveEndEffector_Feedback__rosidl_typesupport_introspection_c__MoveEndEffector_Feedback_message_type_support_handle.typesupport_identifier) {
    a1z_msgs__action__MoveEndEffector_Feedback__rosidl_typesupport_introspection_c__MoveEndEffector_Feedback_message_type_support_handle.typesupport_identifier =
      rosidl_typesupport_introspection_c__identifier;
  }
  return &a1z_msgs__action__MoveEndEffector_Feedback__rosidl_typesupport_introspection_c__MoveEndEffector_Feedback_message_type_support_handle;
}
#ifdef __cplusplus
}
#endif

// already included above
// #include <stddef.h>
// already included above
// #include "a1z_msgs/action/detail/move_end_effector__rosidl_typesupport_introspection_c.h"
// already included above
// #include "a1z_msgs/msg/rosidl_typesupport_introspection_c__visibility_control.h"
// already included above
// #include "rosidl_typesupport_introspection_c/field_types.h"
// already included above
// #include "rosidl_typesupport_introspection_c/identifier.h"
// already included above
// #include "rosidl_typesupport_introspection_c/message_introspection.h"
// already included above
// #include "a1z_msgs/action/detail/move_end_effector__functions.h"
// already included above
// #include "a1z_msgs/action/detail/move_end_effector__struct.h"


// Include directives for member types
// Member `goal_id`
#include "unique_identifier_msgs/msg/uuid.h"
// Member `goal_id`
#include "unique_identifier_msgs/msg/detail/uuid__rosidl_typesupport_introspection_c.h"
// Member `goal`
#include "a1z_msgs/action/move_end_effector.h"
// Member `goal`
// already included above
// #include "a1z_msgs/action/detail/move_end_effector__rosidl_typesupport_introspection_c.h"

#ifdef __cplusplus
extern "C"
{
#endif

void a1z_msgs__action__MoveEndEffector_SendGoal_Request__rosidl_typesupport_introspection_c__MoveEndEffector_SendGoal_Request_init_function(
  void * message_memory, enum rosidl_runtime_c__message_initialization _init)
{
  // TODO(karsten1987): initializers are not yet implemented for typesupport c
  // see https://github.com/ros2/ros2/issues/397
  (void) _init;
  a1z_msgs__action__MoveEndEffector_SendGoal_Request__init(message_memory);
}

void a1z_msgs__action__MoveEndEffector_SendGoal_Request__rosidl_typesupport_introspection_c__MoveEndEffector_SendGoal_Request_fini_function(void * message_memory)
{
  a1z_msgs__action__MoveEndEffector_SendGoal_Request__fini(message_memory);
}

static rosidl_typesupport_introspection_c__MessageMember a1z_msgs__action__MoveEndEffector_SendGoal_Request__rosidl_typesupport_introspection_c__MoveEndEffector_SendGoal_Request_message_member_array[2] = {
  {
    "goal_id",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_MESSAGE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message (initialized later)
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(a1z_msgs__action__MoveEndEffector_SendGoal_Request, goal_id),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "goal",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_MESSAGE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message (initialized later)
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(a1z_msgs__action__MoveEndEffector_SendGoal_Request, goal),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  }
};

static const rosidl_typesupport_introspection_c__MessageMembers a1z_msgs__action__MoveEndEffector_SendGoal_Request__rosidl_typesupport_introspection_c__MoveEndEffector_SendGoal_Request_message_members = {
  "a1z_msgs__action",  // message namespace
  "MoveEndEffector_SendGoal_Request",  // message name
  2,  // number of fields
  sizeof(a1z_msgs__action__MoveEndEffector_SendGoal_Request),
  a1z_msgs__action__MoveEndEffector_SendGoal_Request__rosidl_typesupport_introspection_c__MoveEndEffector_SendGoal_Request_message_member_array,  // message members
  a1z_msgs__action__MoveEndEffector_SendGoal_Request__rosidl_typesupport_introspection_c__MoveEndEffector_SendGoal_Request_init_function,  // function to initialize message memory (memory has to be allocated)
  a1z_msgs__action__MoveEndEffector_SendGoal_Request__rosidl_typesupport_introspection_c__MoveEndEffector_SendGoal_Request_fini_function  // function to terminate message instance (will not free memory)
};

// this is not const since it must be initialized on first access
// since C does not allow non-integral compile-time constants
static rosidl_message_type_support_t a1z_msgs__action__MoveEndEffector_SendGoal_Request__rosidl_typesupport_introspection_c__MoveEndEffector_SendGoal_Request_message_type_support_handle = {
  0,
  &a1z_msgs__action__MoveEndEffector_SendGoal_Request__rosidl_typesupport_introspection_c__MoveEndEffector_SendGoal_Request_message_members,
  get_message_typesupport_handle_function,
};

ROSIDL_TYPESUPPORT_INTROSPECTION_C_EXPORT_a1z_msgs
const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, a1z_msgs, action, MoveEndEffector_SendGoal_Request)() {
  a1z_msgs__action__MoveEndEffector_SendGoal_Request__rosidl_typesupport_introspection_c__MoveEndEffector_SendGoal_Request_message_member_array[0].members_ =
    ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, unique_identifier_msgs, msg, UUID)();
  a1z_msgs__action__MoveEndEffector_SendGoal_Request__rosidl_typesupport_introspection_c__MoveEndEffector_SendGoal_Request_message_member_array[1].members_ =
    ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, a1z_msgs, action, MoveEndEffector_Goal)();
  if (!a1z_msgs__action__MoveEndEffector_SendGoal_Request__rosidl_typesupport_introspection_c__MoveEndEffector_SendGoal_Request_message_type_support_handle.typesupport_identifier) {
    a1z_msgs__action__MoveEndEffector_SendGoal_Request__rosidl_typesupport_introspection_c__MoveEndEffector_SendGoal_Request_message_type_support_handle.typesupport_identifier =
      rosidl_typesupport_introspection_c__identifier;
  }
  return &a1z_msgs__action__MoveEndEffector_SendGoal_Request__rosidl_typesupport_introspection_c__MoveEndEffector_SendGoal_Request_message_type_support_handle;
}
#ifdef __cplusplus
}
#endif

// already included above
// #include <stddef.h>
// already included above
// #include "a1z_msgs/action/detail/move_end_effector__rosidl_typesupport_introspection_c.h"
// already included above
// #include "a1z_msgs/msg/rosidl_typesupport_introspection_c__visibility_control.h"
// already included above
// #include "rosidl_typesupport_introspection_c/field_types.h"
// already included above
// #include "rosidl_typesupport_introspection_c/identifier.h"
// already included above
// #include "rosidl_typesupport_introspection_c/message_introspection.h"
// already included above
// #include "a1z_msgs/action/detail/move_end_effector__functions.h"
// already included above
// #include "a1z_msgs/action/detail/move_end_effector__struct.h"


// Include directives for member types
// Member `stamp`
#include "builtin_interfaces/msg/time.h"
// Member `stamp`
#include "builtin_interfaces/msg/detail/time__rosidl_typesupport_introspection_c.h"

#ifdef __cplusplus
extern "C"
{
#endif

void a1z_msgs__action__MoveEndEffector_SendGoal_Response__rosidl_typesupport_introspection_c__MoveEndEffector_SendGoal_Response_init_function(
  void * message_memory, enum rosidl_runtime_c__message_initialization _init)
{
  // TODO(karsten1987): initializers are not yet implemented for typesupport c
  // see https://github.com/ros2/ros2/issues/397
  (void) _init;
  a1z_msgs__action__MoveEndEffector_SendGoal_Response__init(message_memory);
}

void a1z_msgs__action__MoveEndEffector_SendGoal_Response__rosidl_typesupport_introspection_c__MoveEndEffector_SendGoal_Response_fini_function(void * message_memory)
{
  a1z_msgs__action__MoveEndEffector_SendGoal_Response__fini(message_memory);
}

static rosidl_typesupport_introspection_c__MessageMember a1z_msgs__action__MoveEndEffector_SendGoal_Response__rosidl_typesupport_introspection_c__MoveEndEffector_SendGoal_Response_message_member_array[2] = {
  {
    "accepted",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_BOOLEAN,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(a1z_msgs__action__MoveEndEffector_SendGoal_Response, accepted),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "stamp",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_MESSAGE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message (initialized later)
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(a1z_msgs__action__MoveEndEffector_SendGoal_Response, stamp),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  }
};

static const rosidl_typesupport_introspection_c__MessageMembers a1z_msgs__action__MoveEndEffector_SendGoal_Response__rosidl_typesupport_introspection_c__MoveEndEffector_SendGoal_Response_message_members = {
  "a1z_msgs__action",  // message namespace
  "MoveEndEffector_SendGoal_Response",  // message name
  2,  // number of fields
  sizeof(a1z_msgs__action__MoveEndEffector_SendGoal_Response),
  a1z_msgs__action__MoveEndEffector_SendGoal_Response__rosidl_typesupport_introspection_c__MoveEndEffector_SendGoal_Response_message_member_array,  // message members
  a1z_msgs__action__MoveEndEffector_SendGoal_Response__rosidl_typesupport_introspection_c__MoveEndEffector_SendGoal_Response_init_function,  // function to initialize message memory (memory has to be allocated)
  a1z_msgs__action__MoveEndEffector_SendGoal_Response__rosidl_typesupport_introspection_c__MoveEndEffector_SendGoal_Response_fini_function  // function to terminate message instance (will not free memory)
};

// this is not const since it must be initialized on first access
// since C does not allow non-integral compile-time constants
static rosidl_message_type_support_t a1z_msgs__action__MoveEndEffector_SendGoal_Response__rosidl_typesupport_introspection_c__MoveEndEffector_SendGoal_Response_message_type_support_handle = {
  0,
  &a1z_msgs__action__MoveEndEffector_SendGoal_Response__rosidl_typesupport_introspection_c__MoveEndEffector_SendGoal_Response_message_members,
  get_message_typesupport_handle_function,
};

ROSIDL_TYPESUPPORT_INTROSPECTION_C_EXPORT_a1z_msgs
const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, a1z_msgs, action, MoveEndEffector_SendGoal_Response)() {
  a1z_msgs__action__MoveEndEffector_SendGoal_Response__rosidl_typesupport_introspection_c__MoveEndEffector_SendGoal_Response_message_member_array[1].members_ =
    ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, builtin_interfaces, msg, Time)();
  if (!a1z_msgs__action__MoveEndEffector_SendGoal_Response__rosidl_typesupport_introspection_c__MoveEndEffector_SendGoal_Response_message_type_support_handle.typesupport_identifier) {
    a1z_msgs__action__MoveEndEffector_SendGoal_Response__rosidl_typesupport_introspection_c__MoveEndEffector_SendGoal_Response_message_type_support_handle.typesupport_identifier =
      rosidl_typesupport_introspection_c__identifier;
  }
  return &a1z_msgs__action__MoveEndEffector_SendGoal_Response__rosidl_typesupport_introspection_c__MoveEndEffector_SendGoal_Response_message_type_support_handle;
}
#ifdef __cplusplus
}
#endif

#include "rosidl_runtime_c/service_type_support_struct.h"
// already included above
// #include "a1z_msgs/msg/rosidl_typesupport_introspection_c__visibility_control.h"
// already included above
// #include "a1z_msgs/action/detail/move_end_effector__rosidl_typesupport_introspection_c.h"
// already included above
// #include "rosidl_typesupport_introspection_c/identifier.h"
#include "rosidl_typesupport_introspection_c/service_introspection.h"

// this is intentionally not const to allow initialization later to prevent an initialization race
static rosidl_typesupport_introspection_c__ServiceMembers a1z_msgs__action__detail__move_end_effector__rosidl_typesupport_introspection_c__MoveEndEffector_SendGoal_service_members = {
  "a1z_msgs__action",  // service namespace
  "MoveEndEffector_SendGoal",  // service name
  // these two fields are initialized below on the first access
  NULL,  // request message
  // a1z_msgs__action__detail__move_end_effector__rosidl_typesupport_introspection_c__MoveEndEffector_SendGoal_Request_message_type_support_handle,
  NULL  // response message
  // a1z_msgs__action__detail__move_end_effector__rosidl_typesupport_introspection_c__MoveEndEffector_SendGoal_Response_message_type_support_handle
};

static rosidl_service_type_support_t a1z_msgs__action__detail__move_end_effector__rosidl_typesupport_introspection_c__MoveEndEffector_SendGoal_service_type_support_handle = {
  0,
  &a1z_msgs__action__detail__move_end_effector__rosidl_typesupport_introspection_c__MoveEndEffector_SendGoal_service_members,
  get_service_typesupport_handle_function,
};

// Forward declaration of request/response type support functions
const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, a1z_msgs, action, MoveEndEffector_SendGoal_Request)();

const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, a1z_msgs, action, MoveEndEffector_SendGoal_Response)();

ROSIDL_TYPESUPPORT_INTROSPECTION_C_EXPORT_a1z_msgs
const rosidl_service_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__SERVICE_SYMBOL_NAME(rosidl_typesupport_introspection_c, a1z_msgs, action, MoveEndEffector_SendGoal)() {
  if (!a1z_msgs__action__detail__move_end_effector__rosidl_typesupport_introspection_c__MoveEndEffector_SendGoal_service_type_support_handle.typesupport_identifier) {
    a1z_msgs__action__detail__move_end_effector__rosidl_typesupport_introspection_c__MoveEndEffector_SendGoal_service_type_support_handle.typesupport_identifier =
      rosidl_typesupport_introspection_c__identifier;
  }
  rosidl_typesupport_introspection_c__ServiceMembers * service_members =
    (rosidl_typesupport_introspection_c__ServiceMembers *)a1z_msgs__action__detail__move_end_effector__rosidl_typesupport_introspection_c__MoveEndEffector_SendGoal_service_type_support_handle.data;

  if (!service_members->request_members_) {
    service_members->request_members_ =
      (const rosidl_typesupport_introspection_c__MessageMembers *)
      ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, a1z_msgs, action, MoveEndEffector_SendGoal_Request)()->data;
  }
  if (!service_members->response_members_) {
    service_members->response_members_ =
      (const rosidl_typesupport_introspection_c__MessageMembers *)
      ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, a1z_msgs, action, MoveEndEffector_SendGoal_Response)()->data;
  }

  return &a1z_msgs__action__detail__move_end_effector__rosidl_typesupport_introspection_c__MoveEndEffector_SendGoal_service_type_support_handle;
}

// already included above
// #include <stddef.h>
// already included above
// #include "a1z_msgs/action/detail/move_end_effector__rosidl_typesupport_introspection_c.h"
// already included above
// #include "a1z_msgs/msg/rosidl_typesupport_introspection_c__visibility_control.h"
// already included above
// #include "rosidl_typesupport_introspection_c/field_types.h"
// already included above
// #include "rosidl_typesupport_introspection_c/identifier.h"
// already included above
// #include "rosidl_typesupport_introspection_c/message_introspection.h"
// already included above
// #include "a1z_msgs/action/detail/move_end_effector__functions.h"
// already included above
// #include "a1z_msgs/action/detail/move_end_effector__struct.h"


// Include directives for member types
// Member `goal_id`
// already included above
// #include "unique_identifier_msgs/msg/uuid.h"
// Member `goal_id`
// already included above
// #include "unique_identifier_msgs/msg/detail/uuid__rosidl_typesupport_introspection_c.h"

#ifdef __cplusplus
extern "C"
{
#endif

void a1z_msgs__action__MoveEndEffector_GetResult_Request__rosidl_typesupport_introspection_c__MoveEndEffector_GetResult_Request_init_function(
  void * message_memory, enum rosidl_runtime_c__message_initialization _init)
{
  // TODO(karsten1987): initializers are not yet implemented for typesupport c
  // see https://github.com/ros2/ros2/issues/397
  (void) _init;
  a1z_msgs__action__MoveEndEffector_GetResult_Request__init(message_memory);
}

void a1z_msgs__action__MoveEndEffector_GetResult_Request__rosidl_typesupport_introspection_c__MoveEndEffector_GetResult_Request_fini_function(void * message_memory)
{
  a1z_msgs__action__MoveEndEffector_GetResult_Request__fini(message_memory);
}

static rosidl_typesupport_introspection_c__MessageMember a1z_msgs__action__MoveEndEffector_GetResult_Request__rosidl_typesupport_introspection_c__MoveEndEffector_GetResult_Request_message_member_array[1] = {
  {
    "goal_id",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_MESSAGE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message (initialized later)
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(a1z_msgs__action__MoveEndEffector_GetResult_Request, goal_id),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  }
};

static const rosidl_typesupport_introspection_c__MessageMembers a1z_msgs__action__MoveEndEffector_GetResult_Request__rosidl_typesupport_introspection_c__MoveEndEffector_GetResult_Request_message_members = {
  "a1z_msgs__action",  // message namespace
  "MoveEndEffector_GetResult_Request",  // message name
  1,  // number of fields
  sizeof(a1z_msgs__action__MoveEndEffector_GetResult_Request),
  a1z_msgs__action__MoveEndEffector_GetResult_Request__rosidl_typesupport_introspection_c__MoveEndEffector_GetResult_Request_message_member_array,  // message members
  a1z_msgs__action__MoveEndEffector_GetResult_Request__rosidl_typesupport_introspection_c__MoveEndEffector_GetResult_Request_init_function,  // function to initialize message memory (memory has to be allocated)
  a1z_msgs__action__MoveEndEffector_GetResult_Request__rosidl_typesupport_introspection_c__MoveEndEffector_GetResult_Request_fini_function  // function to terminate message instance (will not free memory)
};

// this is not const since it must be initialized on first access
// since C does not allow non-integral compile-time constants
static rosidl_message_type_support_t a1z_msgs__action__MoveEndEffector_GetResult_Request__rosidl_typesupport_introspection_c__MoveEndEffector_GetResult_Request_message_type_support_handle = {
  0,
  &a1z_msgs__action__MoveEndEffector_GetResult_Request__rosidl_typesupport_introspection_c__MoveEndEffector_GetResult_Request_message_members,
  get_message_typesupport_handle_function,
};

ROSIDL_TYPESUPPORT_INTROSPECTION_C_EXPORT_a1z_msgs
const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, a1z_msgs, action, MoveEndEffector_GetResult_Request)() {
  a1z_msgs__action__MoveEndEffector_GetResult_Request__rosidl_typesupport_introspection_c__MoveEndEffector_GetResult_Request_message_member_array[0].members_ =
    ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, unique_identifier_msgs, msg, UUID)();
  if (!a1z_msgs__action__MoveEndEffector_GetResult_Request__rosidl_typesupport_introspection_c__MoveEndEffector_GetResult_Request_message_type_support_handle.typesupport_identifier) {
    a1z_msgs__action__MoveEndEffector_GetResult_Request__rosidl_typesupport_introspection_c__MoveEndEffector_GetResult_Request_message_type_support_handle.typesupport_identifier =
      rosidl_typesupport_introspection_c__identifier;
  }
  return &a1z_msgs__action__MoveEndEffector_GetResult_Request__rosidl_typesupport_introspection_c__MoveEndEffector_GetResult_Request_message_type_support_handle;
}
#ifdef __cplusplus
}
#endif

// already included above
// #include <stddef.h>
// already included above
// #include "a1z_msgs/action/detail/move_end_effector__rosidl_typesupport_introspection_c.h"
// already included above
// #include "a1z_msgs/msg/rosidl_typesupport_introspection_c__visibility_control.h"
// already included above
// #include "rosidl_typesupport_introspection_c/field_types.h"
// already included above
// #include "rosidl_typesupport_introspection_c/identifier.h"
// already included above
// #include "rosidl_typesupport_introspection_c/message_introspection.h"
// already included above
// #include "a1z_msgs/action/detail/move_end_effector__functions.h"
// already included above
// #include "a1z_msgs/action/detail/move_end_effector__struct.h"


// Include directives for member types
// Member `result`
// already included above
// #include "a1z_msgs/action/move_end_effector.h"
// Member `result`
// already included above
// #include "a1z_msgs/action/detail/move_end_effector__rosidl_typesupport_introspection_c.h"

#ifdef __cplusplus
extern "C"
{
#endif

void a1z_msgs__action__MoveEndEffector_GetResult_Response__rosidl_typesupport_introspection_c__MoveEndEffector_GetResult_Response_init_function(
  void * message_memory, enum rosidl_runtime_c__message_initialization _init)
{
  // TODO(karsten1987): initializers are not yet implemented for typesupport c
  // see https://github.com/ros2/ros2/issues/397
  (void) _init;
  a1z_msgs__action__MoveEndEffector_GetResult_Response__init(message_memory);
}

void a1z_msgs__action__MoveEndEffector_GetResult_Response__rosidl_typesupport_introspection_c__MoveEndEffector_GetResult_Response_fini_function(void * message_memory)
{
  a1z_msgs__action__MoveEndEffector_GetResult_Response__fini(message_memory);
}

static rosidl_typesupport_introspection_c__MessageMember a1z_msgs__action__MoveEndEffector_GetResult_Response__rosidl_typesupport_introspection_c__MoveEndEffector_GetResult_Response_message_member_array[2] = {
  {
    "status",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_INT8,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(a1z_msgs__action__MoveEndEffector_GetResult_Response, status),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "result",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_MESSAGE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message (initialized later)
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(a1z_msgs__action__MoveEndEffector_GetResult_Response, result),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  }
};

static const rosidl_typesupport_introspection_c__MessageMembers a1z_msgs__action__MoveEndEffector_GetResult_Response__rosidl_typesupport_introspection_c__MoveEndEffector_GetResult_Response_message_members = {
  "a1z_msgs__action",  // message namespace
  "MoveEndEffector_GetResult_Response",  // message name
  2,  // number of fields
  sizeof(a1z_msgs__action__MoveEndEffector_GetResult_Response),
  a1z_msgs__action__MoveEndEffector_GetResult_Response__rosidl_typesupport_introspection_c__MoveEndEffector_GetResult_Response_message_member_array,  // message members
  a1z_msgs__action__MoveEndEffector_GetResult_Response__rosidl_typesupport_introspection_c__MoveEndEffector_GetResult_Response_init_function,  // function to initialize message memory (memory has to be allocated)
  a1z_msgs__action__MoveEndEffector_GetResult_Response__rosidl_typesupport_introspection_c__MoveEndEffector_GetResult_Response_fini_function  // function to terminate message instance (will not free memory)
};

// this is not const since it must be initialized on first access
// since C does not allow non-integral compile-time constants
static rosidl_message_type_support_t a1z_msgs__action__MoveEndEffector_GetResult_Response__rosidl_typesupport_introspection_c__MoveEndEffector_GetResult_Response_message_type_support_handle = {
  0,
  &a1z_msgs__action__MoveEndEffector_GetResult_Response__rosidl_typesupport_introspection_c__MoveEndEffector_GetResult_Response_message_members,
  get_message_typesupport_handle_function,
};

ROSIDL_TYPESUPPORT_INTROSPECTION_C_EXPORT_a1z_msgs
const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, a1z_msgs, action, MoveEndEffector_GetResult_Response)() {
  a1z_msgs__action__MoveEndEffector_GetResult_Response__rosidl_typesupport_introspection_c__MoveEndEffector_GetResult_Response_message_member_array[1].members_ =
    ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, a1z_msgs, action, MoveEndEffector_Result)();
  if (!a1z_msgs__action__MoveEndEffector_GetResult_Response__rosidl_typesupport_introspection_c__MoveEndEffector_GetResult_Response_message_type_support_handle.typesupport_identifier) {
    a1z_msgs__action__MoveEndEffector_GetResult_Response__rosidl_typesupport_introspection_c__MoveEndEffector_GetResult_Response_message_type_support_handle.typesupport_identifier =
      rosidl_typesupport_introspection_c__identifier;
  }
  return &a1z_msgs__action__MoveEndEffector_GetResult_Response__rosidl_typesupport_introspection_c__MoveEndEffector_GetResult_Response_message_type_support_handle;
}
#ifdef __cplusplus
}
#endif

// already included above
// #include "rosidl_runtime_c/service_type_support_struct.h"
// already included above
// #include "a1z_msgs/msg/rosidl_typesupport_introspection_c__visibility_control.h"
// already included above
// #include "a1z_msgs/action/detail/move_end_effector__rosidl_typesupport_introspection_c.h"
// already included above
// #include "rosidl_typesupport_introspection_c/identifier.h"
// already included above
// #include "rosidl_typesupport_introspection_c/service_introspection.h"

// this is intentionally not const to allow initialization later to prevent an initialization race
static rosidl_typesupport_introspection_c__ServiceMembers a1z_msgs__action__detail__move_end_effector__rosidl_typesupport_introspection_c__MoveEndEffector_GetResult_service_members = {
  "a1z_msgs__action",  // service namespace
  "MoveEndEffector_GetResult",  // service name
  // these two fields are initialized below on the first access
  NULL,  // request message
  // a1z_msgs__action__detail__move_end_effector__rosidl_typesupport_introspection_c__MoveEndEffector_GetResult_Request_message_type_support_handle,
  NULL  // response message
  // a1z_msgs__action__detail__move_end_effector__rosidl_typesupport_introspection_c__MoveEndEffector_GetResult_Response_message_type_support_handle
};

static rosidl_service_type_support_t a1z_msgs__action__detail__move_end_effector__rosidl_typesupport_introspection_c__MoveEndEffector_GetResult_service_type_support_handle = {
  0,
  &a1z_msgs__action__detail__move_end_effector__rosidl_typesupport_introspection_c__MoveEndEffector_GetResult_service_members,
  get_service_typesupport_handle_function,
};

// Forward declaration of request/response type support functions
const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, a1z_msgs, action, MoveEndEffector_GetResult_Request)();

const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, a1z_msgs, action, MoveEndEffector_GetResult_Response)();

ROSIDL_TYPESUPPORT_INTROSPECTION_C_EXPORT_a1z_msgs
const rosidl_service_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__SERVICE_SYMBOL_NAME(rosidl_typesupport_introspection_c, a1z_msgs, action, MoveEndEffector_GetResult)() {
  if (!a1z_msgs__action__detail__move_end_effector__rosidl_typesupport_introspection_c__MoveEndEffector_GetResult_service_type_support_handle.typesupport_identifier) {
    a1z_msgs__action__detail__move_end_effector__rosidl_typesupport_introspection_c__MoveEndEffector_GetResult_service_type_support_handle.typesupport_identifier =
      rosidl_typesupport_introspection_c__identifier;
  }
  rosidl_typesupport_introspection_c__ServiceMembers * service_members =
    (rosidl_typesupport_introspection_c__ServiceMembers *)a1z_msgs__action__detail__move_end_effector__rosidl_typesupport_introspection_c__MoveEndEffector_GetResult_service_type_support_handle.data;

  if (!service_members->request_members_) {
    service_members->request_members_ =
      (const rosidl_typesupport_introspection_c__MessageMembers *)
      ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, a1z_msgs, action, MoveEndEffector_GetResult_Request)()->data;
  }
  if (!service_members->response_members_) {
    service_members->response_members_ =
      (const rosidl_typesupport_introspection_c__MessageMembers *)
      ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, a1z_msgs, action, MoveEndEffector_GetResult_Response)()->data;
  }

  return &a1z_msgs__action__detail__move_end_effector__rosidl_typesupport_introspection_c__MoveEndEffector_GetResult_service_type_support_handle;
}

// already included above
// #include <stddef.h>
// already included above
// #include "a1z_msgs/action/detail/move_end_effector__rosidl_typesupport_introspection_c.h"
// already included above
// #include "a1z_msgs/msg/rosidl_typesupport_introspection_c__visibility_control.h"
// already included above
// #include "rosidl_typesupport_introspection_c/field_types.h"
// already included above
// #include "rosidl_typesupport_introspection_c/identifier.h"
// already included above
// #include "rosidl_typesupport_introspection_c/message_introspection.h"
// already included above
// #include "a1z_msgs/action/detail/move_end_effector__functions.h"
// already included above
// #include "a1z_msgs/action/detail/move_end_effector__struct.h"


// Include directives for member types
// Member `goal_id`
// already included above
// #include "unique_identifier_msgs/msg/uuid.h"
// Member `goal_id`
// already included above
// #include "unique_identifier_msgs/msg/detail/uuid__rosidl_typesupport_introspection_c.h"
// Member `feedback`
// already included above
// #include "a1z_msgs/action/move_end_effector.h"
// Member `feedback`
// already included above
// #include "a1z_msgs/action/detail/move_end_effector__rosidl_typesupport_introspection_c.h"

#ifdef __cplusplus
extern "C"
{
#endif

void a1z_msgs__action__MoveEndEffector_FeedbackMessage__rosidl_typesupport_introspection_c__MoveEndEffector_FeedbackMessage_init_function(
  void * message_memory, enum rosidl_runtime_c__message_initialization _init)
{
  // TODO(karsten1987): initializers are not yet implemented for typesupport c
  // see https://github.com/ros2/ros2/issues/397
  (void) _init;
  a1z_msgs__action__MoveEndEffector_FeedbackMessage__init(message_memory);
}

void a1z_msgs__action__MoveEndEffector_FeedbackMessage__rosidl_typesupport_introspection_c__MoveEndEffector_FeedbackMessage_fini_function(void * message_memory)
{
  a1z_msgs__action__MoveEndEffector_FeedbackMessage__fini(message_memory);
}

static rosidl_typesupport_introspection_c__MessageMember a1z_msgs__action__MoveEndEffector_FeedbackMessage__rosidl_typesupport_introspection_c__MoveEndEffector_FeedbackMessage_message_member_array[2] = {
  {
    "goal_id",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_MESSAGE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message (initialized later)
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(a1z_msgs__action__MoveEndEffector_FeedbackMessage, goal_id),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "feedback",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_MESSAGE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message (initialized later)
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(a1z_msgs__action__MoveEndEffector_FeedbackMessage, feedback),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  }
};

static const rosidl_typesupport_introspection_c__MessageMembers a1z_msgs__action__MoveEndEffector_FeedbackMessage__rosidl_typesupport_introspection_c__MoveEndEffector_FeedbackMessage_message_members = {
  "a1z_msgs__action",  // message namespace
  "MoveEndEffector_FeedbackMessage",  // message name
  2,  // number of fields
  sizeof(a1z_msgs__action__MoveEndEffector_FeedbackMessage),
  a1z_msgs__action__MoveEndEffector_FeedbackMessage__rosidl_typesupport_introspection_c__MoveEndEffector_FeedbackMessage_message_member_array,  // message members
  a1z_msgs__action__MoveEndEffector_FeedbackMessage__rosidl_typesupport_introspection_c__MoveEndEffector_FeedbackMessage_init_function,  // function to initialize message memory (memory has to be allocated)
  a1z_msgs__action__MoveEndEffector_FeedbackMessage__rosidl_typesupport_introspection_c__MoveEndEffector_FeedbackMessage_fini_function  // function to terminate message instance (will not free memory)
};

// this is not const since it must be initialized on first access
// since C does not allow non-integral compile-time constants
static rosidl_message_type_support_t a1z_msgs__action__MoveEndEffector_FeedbackMessage__rosidl_typesupport_introspection_c__MoveEndEffector_FeedbackMessage_message_type_support_handle = {
  0,
  &a1z_msgs__action__MoveEndEffector_FeedbackMessage__rosidl_typesupport_introspection_c__MoveEndEffector_FeedbackMessage_message_members,
  get_message_typesupport_handle_function,
};

ROSIDL_TYPESUPPORT_INTROSPECTION_C_EXPORT_a1z_msgs
const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, a1z_msgs, action, MoveEndEffector_FeedbackMessage)() {
  a1z_msgs__action__MoveEndEffector_FeedbackMessage__rosidl_typesupport_introspection_c__MoveEndEffector_FeedbackMessage_message_member_array[0].members_ =
    ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, unique_identifier_msgs, msg, UUID)();
  a1z_msgs__action__MoveEndEffector_FeedbackMessage__rosidl_typesupport_introspection_c__MoveEndEffector_FeedbackMessage_message_member_array[1].members_ =
    ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, a1z_msgs, action, MoveEndEffector_Feedback)();
  if (!a1z_msgs__action__MoveEndEffector_FeedbackMessage__rosidl_typesupport_introspection_c__MoveEndEffector_FeedbackMessage_message_type_support_handle.typesupport_identifier) {
    a1z_msgs__action__MoveEndEffector_FeedbackMessage__rosidl_typesupport_introspection_c__MoveEndEffector_FeedbackMessage_message_type_support_handle.typesupport_identifier =
      rosidl_typesupport_introspection_c__identifier;
  }
  return &a1z_msgs__action__MoveEndEffector_FeedbackMessage__rosidl_typesupport_introspection_c__MoveEndEffector_FeedbackMessage_message_type_support_handle;
}
#ifdef __cplusplus
}
#endif
