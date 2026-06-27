// generated from rosidl_generator_c/resource/idl__struct.h.em
// with input from a1z_msgs:action/MoveEndEffector.idl
// generated code does not contain a copyright notice

#ifndef A1Z_MSGS__ACTION__DETAIL__MOVE_END_EFFECTOR__STRUCT_H_
#define A1Z_MSGS__ACTION__DETAIL__MOVE_END_EFFECTOR__STRUCT_H_

#ifdef __cplusplus
extern "C"
{
#endif

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>


// Constants defined in the message

// Include directives for member types
// Member 'goal_pose'
#include "geometry_msgs/msg/detail/pose_stamped__struct.h"
// Member 'end_effector_frame'
#include "rosidl_runtime_c/string.h"

/// Struct defined in action/MoveEndEffector in the package a1z_msgs.
typedef struct a1z_msgs__action__MoveEndEffector_Goal
{
  geometry_msgs__msg__PoseStamped goal_pose;
  rosidl_runtime_c__String end_effector_frame;
  bool command_gripper;
  float gripper_opening;
  float speed;
  float position_tolerance_m;
  float orientation_tolerance_rad;
  float joint_margin_rad;
  float max_joint_step_rad;
  float min_target_z_m;
  float max_target_z_m;
} a1z_msgs__action__MoveEndEffector_Goal;

// Struct for a sequence of a1z_msgs__action__MoveEndEffector_Goal.
typedef struct a1z_msgs__action__MoveEndEffector_Goal__Sequence
{
  a1z_msgs__action__MoveEndEffector_Goal * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} a1z_msgs__action__MoveEndEffector_Goal__Sequence;


// Constants defined in the message

// Include directives for member types
// Member 'status'
// Member 'failure_reason'
// already included above
// #include "rosidl_runtime_c/string.h"
// Member 'final_joint_positions_rad'
#include "rosidl_runtime_c/primitives_sequence.h"
// Member 'final_pose'
// already included above
// #include "geometry_msgs/msg/detail/pose_stamped__struct.h"

/// Struct defined in action/MoveEndEffector in the package a1z_msgs.
typedef struct a1z_msgs__action__MoveEndEffector_Result
{
  bool success;
  rosidl_runtime_c__String status;
  rosidl_runtime_c__String failure_reason;
  rosidl_runtime_c__double__Sequence final_joint_positions_rad;
  geometry_msgs__msg__PoseStamped final_pose;
  float final_gripper_opening;
  bool ik_converged;
  float position_error_m;
  float orientation_error_rad;
} a1z_msgs__action__MoveEndEffector_Result;

// Struct for a sequence of a1z_msgs__action__MoveEndEffector_Result.
typedef struct a1z_msgs__action__MoveEndEffector_Result__Sequence
{
  a1z_msgs__action__MoveEndEffector_Result * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} a1z_msgs__action__MoveEndEffector_Result__Sequence;


// Constants defined in the message

// Include directives for member types
// Member 'stage'
// Member 'message'
// already included above
// #include "rosidl_runtime_c/string.h"

/// Struct defined in action/MoveEndEffector in the package a1z_msgs.
typedef struct a1z_msgs__action__MoveEndEffector_Feedback
{
  rosidl_runtime_c__String stage;
  rosidl_runtime_c__String message;
} a1z_msgs__action__MoveEndEffector_Feedback;

// Struct for a sequence of a1z_msgs__action__MoveEndEffector_Feedback.
typedef struct a1z_msgs__action__MoveEndEffector_Feedback__Sequence
{
  a1z_msgs__action__MoveEndEffector_Feedback * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} a1z_msgs__action__MoveEndEffector_Feedback__Sequence;


// Constants defined in the message

// Include directives for member types
// Member 'goal_id'
#include "unique_identifier_msgs/msg/detail/uuid__struct.h"
// Member 'goal'
#include "a1z_msgs/action/detail/move_end_effector__struct.h"

/// Struct defined in action/MoveEndEffector in the package a1z_msgs.
typedef struct a1z_msgs__action__MoveEndEffector_SendGoal_Request
{
  unique_identifier_msgs__msg__UUID goal_id;
  a1z_msgs__action__MoveEndEffector_Goal goal;
} a1z_msgs__action__MoveEndEffector_SendGoal_Request;

// Struct for a sequence of a1z_msgs__action__MoveEndEffector_SendGoal_Request.
typedef struct a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence
{
  a1z_msgs__action__MoveEndEffector_SendGoal_Request * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence;


// Constants defined in the message

// Include directives for member types
// Member 'stamp'
#include "builtin_interfaces/msg/detail/time__struct.h"

/// Struct defined in action/MoveEndEffector in the package a1z_msgs.
typedef struct a1z_msgs__action__MoveEndEffector_SendGoal_Response
{
  bool accepted;
  builtin_interfaces__msg__Time stamp;
} a1z_msgs__action__MoveEndEffector_SendGoal_Response;

// Struct for a sequence of a1z_msgs__action__MoveEndEffector_SendGoal_Response.
typedef struct a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence
{
  a1z_msgs__action__MoveEndEffector_SendGoal_Response * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence;


// Constants defined in the message

// Include directives for member types
// Member 'goal_id'
// already included above
// #include "unique_identifier_msgs/msg/detail/uuid__struct.h"

/// Struct defined in action/MoveEndEffector in the package a1z_msgs.
typedef struct a1z_msgs__action__MoveEndEffector_GetResult_Request
{
  unique_identifier_msgs__msg__UUID goal_id;
} a1z_msgs__action__MoveEndEffector_GetResult_Request;

// Struct for a sequence of a1z_msgs__action__MoveEndEffector_GetResult_Request.
typedef struct a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence
{
  a1z_msgs__action__MoveEndEffector_GetResult_Request * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence;


// Constants defined in the message

// Include directives for member types
// Member 'result'
// already included above
// #include "a1z_msgs/action/detail/move_end_effector__struct.h"

/// Struct defined in action/MoveEndEffector in the package a1z_msgs.
typedef struct a1z_msgs__action__MoveEndEffector_GetResult_Response
{
  int8_t status;
  a1z_msgs__action__MoveEndEffector_Result result;
} a1z_msgs__action__MoveEndEffector_GetResult_Response;

// Struct for a sequence of a1z_msgs__action__MoveEndEffector_GetResult_Response.
typedef struct a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence
{
  a1z_msgs__action__MoveEndEffector_GetResult_Response * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence;


// Constants defined in the message

// Include directives for member types
// Member 'goal_id'
// already included above
// #include "unique_identifier_msgs/msg/detail/uuid__struct.h"
// Member 'feedback'
// already included above
// #include "a1z_msgs/action/detail/move_end_effector__struct.h"

/// Struct defined in action/MoveEndEffector in the package a1z_msgs.
typedef struct a1z_msgs__action__MoveEndEffector_FeedbackMessage
{
  unique_identifier_msgs__msg__UUID goal_id;
  a1z_msgs__action__MoveEndEffector_Feedback feedback;
} a1z_msgs__action__MoveEndEffector_FeedbackMessage;

// Struct for a sequence of a1z_msgs__action__MoveEndEffector_FeedbackMessage.
typedef struct a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence
{
  a1z_msgs__action__MoveEndEffector_FeedbackMessage * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence;

#ifdef __cplusplus
}
#endif

#endif  // A1Z_MSGS__ACTION__DETAIL__MOVE_END_EFFECTOR__STRUCT_H_
