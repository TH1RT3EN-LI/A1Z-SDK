// generated from rosidl_generator_cpp/resource/idl__traits.hpp.em
// with input from a1z_msgs:action/MoveEndEffector.idl
// generated code does not contain a copyright notice

#ifndef A1Z_MSGS__ACTION__DETAIL__MOVE_END_EFFECTOR__TRAITS_HPP_
#define A1Z_MSGS__ACTION__DETAIL__MOVE_END_EFFECTOR__TRAITS_HPP_

#include <stdint.h>

#include <sstream>
#include <string>
#include <type_traits>

#include "a1z_msgs/action/detail/move_end_effector__struct.hpp"
#include "rosidl_runtime_cpp/traits.hpp"

// Include directives for member types
// Member 'goal_pose'
#include "geometry_msgs/msg/detail/pose_stamped__traits.hpp"

namespace a1z_msgs
{

namespace action
{

inline void to_flow_style_yaml(
  const MoveEndEffector_Goal & msg,
  std::ostream & out)
{
  out << "{";
  // member: goal_pose
  {
    out << "goal_pose: ";
    to_flow_style_yaml(msg.goal_pose, out);
    out << ", ";
  }

  // member: end_effector_frame
  {
    out << "end_effector_frame: ";
    rosidl_generator_traits::value_to_yaml(msg.end_effector_frame, out);
    out << ", ";
  }

  // member: command_gripper
  {
    out << "command_gripper: ";
    rosidl_generator_traits::value_to_yaml(msg.command_gripper, out);
    out << ", ";
  }

  // member: gripper_opening
  {
    out << "gripper_opening: ";
    rosidl_generator_traits::value_to_yaml(msg.gripper_opening, out);
    out << ", ";
  }

  // member: speed
  {
    out << "speed: ";
    rosidl_generator_traits::value_to_yaml(msg.speed, out);
    out << ", ";
  }

  // member: position_tolerance_m
  {
    out << "position_tolerance_m: ";
    rosidl_generator_traits::value_to_yaml(msg.position_tolerance_m, out);
    out << ", ";
  }

  // member: orientation_tolerance_rad
  {
    out << "orientation_tolerance_rad: ";
    rosidl_generator_traits::value_to_yaml(msg.orientation_tolerance_rad, out);
    out << ", ";
  }

  // member: joint_margin_rad
  {
    out << "joint_margin_rad: ";
    rosidl_generator_traits::value_to_yaml(msg.joint_margin_rad, out);
    out << ", ";
  }

  // member: max_joint_step_rad
  {
    out << "max_joint_step_rad: ";
    rosidl_generator_traits::value_to_yaml(msg.max_joint_step_rad, out);
    out << ", ";
  }

  // member: min_target_z_m
  {
    out << "min_target_z_m: ";
    rosidl_generator_traits::value_to_yaml(msg.min_target_z_m, out);
    out << ", ";
  }

  // member: max_target_z_m
  {
    out << "max_target_z_m: ";
    rosidl_generator_traits::value_to_yaml(msg.max_target_z_m, out);
  }
  out << "}";
}  // NOLINT(readability/fn_size)

inline void to_block_style_yaml(
  const MoveEndEffector_Goal & msg,
  std::ostream & out, size_t indentation = 0)
{
  // member: goal_pose
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "goal_pose:\n";
    to_block_style_yaml(msg.goal_pose, out, indentation + 2);
  }

  // member: end_effector_frame
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "end_effector_frame: ";
    rosidl_generator_traits::value_to_yaml(msg.end_effector_frame, out);
    out << "\n";
  }

  // member: command_gripper
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "command_gripper: ";
    rosidl_generator_traits::value_to_yaml(msg.command_gripper, out);
    out << "\n";
  }

  // member: gripper_opening
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "gripper_opening: ";
    rosidl_generator_traits::value_to_yaml(msg.gripper_opening, out);
    out << "\n";
  }

  // member: speed
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "speed: ";
    rosidl_generator_traits::value_to_yaml(msg.speed, out);
    out << "\n";
  }

  // member: position_tolerance_m
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "position_tolerance_m: ";
    rosidl_generator_traits::value_to_yaml(msg.position_tolerance_m, out);
    out << "\n";
  }

  // member: orientation_tolerance_rad
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "orientation_tolerance_rad: ";
    rosidl_generator_traits::value_to_yaml(msg.orientation_tolerance_rad, out);
    out << "\n";
  }

  // member: joint_margin_rad
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "joint_margin_rad: ";
    rosidl_generator_traits::value_to_yaml(msg.joint_margin_rad, out);
    out << "\n";
  }

  // member: max_joint_step_rad
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "max_joint_step_rad: ";
    rosidl_generator_traits::value_to_yaml(msg.max_joint_step_rad, out);
    out << "\n";
  }

  // member: min_target_z_m
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "min_target_z_m: ";
    rosidl_generator_traits::value_to_yaml(msg.min_target_z_m, out);
    out << "\n";
  }

  // member: max_target_z_m
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "max_target_z_m: ";
    rosidl_generator_traits::value_to_yaml(msg.max_target_z_m, out);
    out << "\n";
  }
}  // NOLINT(readability/fn_size)

inline std::string to_yaml(const MoveEndEffector_Goal & msg, bool use_flow_style = false)
{
  std::ostringstream out;
  if (use_flow_style) {
    to_flow_style_yaml(msg, out);
  } else {
    to_block_style_yaml(msg, out);
  }
  return out.str();
}

}  // namespace action

}  // namespace a1z_msgs

namespace rosidl_generator_traits
{

[[deprecated("use a1z_msgs::action::to_block_style_yaml() instead")]]
inline void to_yaml(
  const a1z_msgs::action::MoveEndEffector_Goal & msg,
  std::ostream & out, size_t indentation = 0)
{
  a1z_msgs::action::to_block_style_yaml(msg, out, indentation);
}

[[deprecated("use a1z_msgs::action::to_yaml() instead")]]
inline std::string to_yaml(const a1z_msgs::action::MoveEndEffector_Goal & msg)
{
  return a1z_msgs::action::to_yaml(msg);
}

template<>
inline const char * data_type<a1z_msgs::action::MoveEndEffector_Goal>()
{
  return "a1z_msgs::action::MoveEndEffector_Goal";
}

template<>
inline const char * name<a1z_msgs::action::MoveEndEffector_Goal>()
{
  return "a1z_msgs/action/MoveEndEffector_Goal";
}

template<>
struct has_fixed_size<a1z_msgs::action::MoveEndEffector_Goal>
  : std::integral_constant<bool, false> {};

template<>
struct has_bounded_size<a1z_msgs::action::MoveEndEffector_Goal>
  : std::integral_constant<bool, false> {};

template<>
struct is_message<a1z_msgs::action::MoveEndEffector_Goal>
  : std::true_type {};

}  // namespace rosidl_generator_traits

// Include directives for member types
// Member 'final_pose'
// already included above
// #include "geometry_msgs/msg/detail/pose_stamped__traits.hpp"

namespace a1z_msgs
{

namespace action
{

inline void to_flow_style_yaml(
  const MoveEndEffector_Result & msg,
  std::ostream & out)
{
  out << "{";
  // member: success
  {
    out << "success: ";
    rosidl_generator_traits::value_to_yaml(msg.success, out);
    out << ", ";
  }

  // member: status
  {
    out << "status: ";
    rosidl_generator_traits::value_to_yaml(msg.status, out);
    out << ", ";
  }

  // member: failure_reason
  {
    out << "failure_reason: ";
    rosidl_generator_traits::value_to_yaml(msg.failure_reason, out);
    out << ", ";
  }

  // member: final_joint_positions_rad
  {
    if (msg.final_joint_positions_rad.size() == 0) {
      out << "final_joint_positions_rad: []";
    } else {
      out << "final_joint_positions_rad: [";
      size_t pending_items = msg.final_joint_positions_rad.size();
      for (auto item : msg.final_joint_positions_rad) {
        rosidl_generator_traits::value_to_yaml(item, out);
        if (--pending_items > 0) {
          out << ", ";
        }
      }
      out << "]";
    }
    out << ", ";
  }

  // member: final_pose
  {
    out << "final_pose: ";
    to_flow_style_yaml(msg.final_pose, out);
    out << ", ";
  }

  // member: final_gripper_opening
  {
    out << "final_gripper_opening: ";
    rosidl_generator_traits::value_to_yaml(msg.final_gripper_opening, out);
    out << ", ";
  }

  // member: ik_converged
  {
    out << "ik_converged: ";
    rosidl_generator_traits::value_to_yaml(msg.ik_converged, out);
    out << ", ";
  }

  // member: position_error_m
  {
    out << "position_error_m: ";
    rosidl_generator_traits::value_to_yaml(msg.position_error_m, out);
    out << ", ";
  }

  // member: orientation_error_rad
  {
    out << "orientation_error_rad: ";
    rosidl_generator_traits::value_to_yaml(msg.orientation_error_rad, out);
  }
  out << "}";
}  // NOLINT(readability/fn_size)

inline void to_block_style_yaml(
  const MoveEndEffector_Result & msg,
  std::ostream & out, size_t indentation = 0)
{
  // member: success
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "success: ";
    rosidl_generator_traits::value_to_yaml(msg.success, out);
    out << "\n";
  }

  // member: status
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "status: ";
    rosidl_generator_traits::value_to_yaml(msg.status, out);
    out << "\n";
  }

  // member: failure_reason
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "failure_reason: ";
    rosidl_generator_traits::value_to_yaml(msg.failure_reason, out);
    out << "\n";
  }

  // member: final_joint_positions_rad
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    if (msg.final_joint_positions_rad.size() == 0) {
      out << "final_joint_positions_rad: []\n";
    } else {
      out << "final_joint_positions_rad:\n";
      for (auto item : msg.final_joint_positions_rad) {
        if (indentation > 0) {
          out << std::string(indentation, ' ');
        }
        out << "- ";
        rosidl_generator_traits::value_to_yaml(item, out);
        out << "\n";
      }
    }
  }

  // member: final_pose
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "final_pose:\n";
    to_block_style_yaml(msg.final_pose, out, indentation + 2);
  }

  // member: final_gripper_opening
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "final_gripper_opening: ";
    rosidl_generator_traits::value_to_yaml(msg.final_gripper_opening, out);
    out << "\n";
  }

  // member: ik_converged
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "ik_converged: ";
    rosidl_generator_traits::value_to_yaml(msg.ik_converged, out);
    out << "\n";
  }

  // member: position_error_m
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "position_error_m: ";
    rosidl_generator_traits::value_to_yaml(msg.position_error_m, out);
    out << "\n";
  }

  // member: orientation_error_rad
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "orientation_error_rad: ";
    rosidl_generator_traits::value_to_yaml(msg.orientation_error_rad, out);
    out << "\n";
  }
}  // NOLINT(readability/fn_size)

inline std::string to_yaml(const MoveEndEffector_Result & msg, bool use_flow_style = false)
{
  std::ostringstream out;
  if (use_flow_style) {
    to_flow_style_yaml(msg, out);
  } else {
    to_block_style_yaml(msg, out);
  }
  return out.str();
}

}  // namespace action

}  // namespace a1z_msgs

namespace rosidl_generator_traits
{

[[deprecated("use a1z_msgs::action::to_block_style_yaml() instead")]]
inline void to_yaml(
  const a1z_msgs::action::MoveEndEffector_Result & msg,
  std::ostream & out, size_t indentation = 0)
{
  a1z_msgs::action::to_block_style_yaml(msg, out, indentation);
}

[[deprecated("use a1z_msgs::action::to_yaml() instead")]]
inline std::string to_yaml(const a1z_msgs::action::MoveEndEffector_Result & msg)
{
  return a1z_msgs::action::to_yaml(msg);
}

template<>
inline const char * data_type<a1z_msgs::action::MoveEndEffector_Result>()
{
  return "a1z_msgs::action::MoveEndEffector_Result";
}

template<>
inline const char * name<a1z_msgs::action::MoveEndEffector_Result>()
{
  return "a1z_msgs/action/MoveEndEffector_Result";
}

template<>
struct has_fixed_size<a1z_msgs::action::MoveEndEffector_Result>
  : std::integral_constant<bool, false> {};

template<>
struct has_bounded_size<a1z_msgs::action::MoveEndEffector_Result>
  : std::integral_constant<bool, false> {};

template<>
struct is_message<a1z_msgs::action::MoveEndEffector_Result>
  : std::true_type {};

}  // namespace rosidl_generator_traits

namespace a1z_msgs
{

namespace action
{

inline void to_flow_style_yaml(
  const MoveEndEffector_Feedback & msg,
  std::ostream & out)
{
  out << "{";
  // member: stage
  {
    out << "stage: ";
    rosidl_generator_traits::value_to_yaml(msg.stage, out);
    out << ", ";
  }

  // member: message
  {
    out << "message: ";
    rosidl_generator_traits::value_to_yaml(msg.message, out);
  }
  out << "}";
}  // NOLINT(readability/fn_size)

inline void to_block_style_yaml(
  const MoveEndEffector_Feedback & msg,
  std::ostream & out, size_t indentation = 0)
{
  // member: stage
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "stage: ";
    rosidl_generator_traits::value_to_yaml(msg.stage, out);
    out << "\n";
  }

  // member: message
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "message: ";
    rosidl_generator_traits::value_to_yaml(msg.message, out);
    out << "\n";
  }
}  // NOLINT(readability/fn_size)

inline std::string to_yaml(const MoveEndEffector_Feedback & msg, bool use_flow_style = false)
{
  std::ostringstream out;
  if (use_flow_style) {
    to_flow_style_yaml(msg, out);
  } else {
    to_block_style_yaml(msg, out);
  }
  return out.str();
}

}  // namespace action

}  // namespace a1z_msgs

namespace rosidl_generator_traits
{

[[deprecated("use a1z_msgs::action::to_block_style_yaml() instead")]]
inline void to_yaml(
  const a1z_msgs::action::MoveEndEffector_Feedback & msg,
  std::ostream & out, size_t indentation = 0)
{
  a1z_msgs::action::to_block_style_yaml(msg, out, indentation);
}

[[deprecated("use a1z_msgs::action::to_yaml() instead")]]
inline std::string to_yaml(const a1z_msgs::action::MoveEndEffector_Feedback & msg)
{
  return a1z_msgs::action::to_yaml(msg);
}

template<>
inline const char * data_type<a1z_msgs::action::MoveEndEffector_Feedback>()
{
  return "a1z_msgs::action::MoveEndEffector_Feedback";
}

template<>
inline const char * name<a1z_msgs::action::MoveEndEffector_Feedback>()
{
  return "a1z_msgs/action/MoveEndEffector_Feedback";
}

template<>
struct has_fixed_size<a1z_msgs::action::MoveEndEffector_Feedback>
  : std::integral_constant<bool, false> {};

template<>
struct has_bounded_size<a1z_msgs::action::MoveEndEffector_Feedback>
  : std::integral_constant<bool, false> {};

template<>
struct is_message<a1z_msgs::action::MoveEndEffector_Feedback>
  : std::true_type {};

}  // namespace rosidl_generator_traits

// Include directives for member types
// Member 'goal_id'
#include "unique_identifier_msgs/msg/detail/uuid__traits.hpp"
// Member 'goal'
#include "a1z_msgs/action/detail/move_end_effector__traits.hpp"

namespace a1z_msgs
{

namespace action
{

inline void to_flow_style_yaml(
  const MoveEndEffector_SendGoal_Request & msg,
  std::ostream & out)
{
  out << "{";
  // member: goal_id
  {
    out << "goal_id: ";
    to_flow_style_yaml(msg.goal_id, out);
    out << ", ";
  }

  // member: goal
  {
    out << "goal: ";
    to_flow_style_yaml(msg.goal, out);
  }
  out << "}";
}  // NOLINT(readability/fn_size)

inline void to_block_style_yaml(
  const MoveEndEffector_SendGoal_Request & msg,
  std::ostream & out, size_t indentation = 0)
{
  // member: goal_id
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "goal_id:\n";
    to_block_style_yaml(msg.goal_id, out, indentation + 2);
  }

  // member: goal
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "goal:\n";
    to_block_style_yaml(msg.goal, out, indentation + 2);
  }
}  // NOLINT(readability/fn_size)

inline std::string to_yaml(const MoveEndEffector_SendGoal_Request & msg, bool use_flow_style = false)
{
  std::ostringstream out;
  if (use_flow_style) {
    to_flow_style_yaml(msg, out);
  } else {
    to_block_style_yaml(msg, out);
  }
  return out.str();
}

}  // namespace action

}  // namespace a1z_msgs

namespace rosidl_generator_traits
{

[[deprecated("use a1z_msgs::action::to_block_style_yaml() instead")]]
inline void to_yaml(
  const a1z_msgs::action::MoveEndEffector_SendGoal_Request & msg,
  std::ostream & out, size_t indentation = 0)
{
  a1z_msgs::action::to_block_style_yaml(msg, out, indentation);
}

[[deprecated("use a1z_msgs::action::to_yaml() instead")]]
inline std::string to_yaml(const a1z_msgs::action::MoveEndEffector_SendGoal_Request & msg)
{
  return a1z_msgs::action::to_yaml(msg);
}

template<>
inline const char * data_type<a1z_msgs::action::MoveEndEffector_SendGoal_Request>()
{
  return "a1z_msgs::action::MoveEndEffector_SendGoal_Request";
}

template<>
inline const char * name<a1z_msgs::action::MoveEndEffector_SendGoal_Request>()
{
  return "a1z_msgs/action/MoveEndEffector_SendGoal_Request";
}

template<>
struct has_fixed_size<a1z_msgs::action::MoveEndEffector_SendGoal_Request>
  : std::integral_constant<bool, has_fixed_size<a1z_msgs::action::MoveEndEffector_Goal>::value && has_fixed_size<unique_identifier_msgs::msg::UUID>::value> {};

template<>
struct has_bounded_size<a1z_msgs::action::MoveEndEffector_SendGoal_Request>
  : std::integral_constant<bool, has_bounded_size<a1z_msgs::action::MoveEndEffector_Goal>::value && has_bounded_size<unique_identifier_msgs::msg::UUID>::value> {};

template<>
struct is_message<a1z_msgs::action::MoveEndEffector_SendGoal_Request>
  : std::true_type {};

}  // namespace rosidl_generator_traits

// Include directives for member types
// Member 'stamp'
#include "builtin_interfaces/msg/detail/time__traits.hpp"

namespace a1z_msgs
{

namespace action
{

inline void to_flow_style_yaml(
  const MoveEndEffector_SendGoal_Response & msg,
  std::ostream & out)
{
  out << "{";
  // member: accepted
  {
    out << "accepted: ";
    rosidl_generator_traits::value_to_yaml(msg.accepted, out);
    out << ", ";
  }

  // member: stamp
  {
    out << "stamp: ";
    to_flow_style_yaml(msg.stamp, out);
  }
  out << "}";
}  // NOLINT(readability/fn_size)

inline void to_block_style_yaml(
  const MoveEndEffector_SendGoal_Response & msg,
  std::ostream & out, size_t indentation = 0)
{
  // member: accepted
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "accepted: ";
    rosidl_generator_traits::value_to_yaml(msg.accepted, out);
    out << "\n";
  }

  // member: stamp
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "stamp:\n";
    to_block_style_yaml(msg.stamp, out, indentation + 2);
  }
}  // NOLINT(readability/fn_size)

inline std::string to_yaml(const MoveEndEffector_SendGoal_Response & msg, bool use_flow_style = false)
{
  std::ostringstream out;
  if (use_flow_style) {
    to_flow_style_yaml(msg, out);
  } else {
    to_block_style_yaml(msg, out);
  }
  return out.str();
}

}  // namespace action

}  // namespace a1z_msgs

namespace rosidl_generator_traits
{

[[deprecated("use a1z_msgs::action::to_block_style_yaml() instead")]]
inline void to_yaml(
  const a1z_msgs::action::MoveEndEffector_SendGoal_Response & msg,
  std::ostream & out, size_t indentation = 0)
{
  a1z_msgs::action::to_block_style_yaml(msg, out, indentation);
}

[[deprecated("use a1z_msgs::action::to_yaml() instead")]]
inline std::string to_yaml(const a1z_msgs::action::MoveEndEffector_SendGoal_Response & msg)
{
  return a1z_msgs::action::to_yaml(msg);
}

template<>
inline const char * data_type<a1z_msgs::action::MoveEndEffector_SendGoal_Response>()
{
  return "a1z_msgs::action::MoveEndEffector_SendGoal_Response";
}

template<>
inline const char * name<a1z_msgs::action::MoveEndEffector_SendGoal_Response>()
{
  return "a1z_msgs/action/MoveEndEffector_SendGoal_Response";
}

template<>
struct has_fixed_size<a1z_msgs::action::MoveEndEffector_SendGoal_Response>
  : std::integral_constant<bool, has_fixed_size<builtin_interfaces::msg::Time>::value> {};

template<>
struct has_bounded_size<a1z_msgs::action::MoveEndEffector_SendGoal_Response>
  : std::integral_constant<bool, has_bounded_size<builtin_interfaces::msg::Time>::value> {};

template<>
struct is_message<a1z_msgs::action::MoveEndEffector_SendGoal_Response>
  : std::true_type {};

}  // namespace rosidl_generator_traits

namespace rosidl_generator_traits
{

template<>
inline const char * data_type<a1z_msgs::action::MoveEndEffector_SendGoal>()
{
  return "a1z_msgs::action::MoveEndEffector_SendGoal";
}

template<>
inline const char * name<a1z_msgs::action::MoveEndEffector_SendGoal>()
{
  return "a1z_msgs/action/MoveEndEffector_SendGoal";
}

template<>
struct has_fixed_size<a1z_msgs::action::MoveEndEffector_SendGoal>
  : std::integral_constant<
    bool,
    has_fixed_size<a1z_msgs::action::MoveEndEffector_SendGoal_Request>::value &&
    has_fixed_size<a1z_msgs::action::MoveEndEffector_SendGoal_Response>::value
  >
{
};

template<>
struct has_bounded_size<a1z_msgs::action::MoveEndEffector_SendGoal>
  : std::integral_constant<
    bool,
    has_bounded_size<a1z_msgs::action::MoveEndEffector_SendGoal_Request>::value &&
    has_bounded_size<a1z_msgs::action::MoveEndEffector_SendGoal_Response>::value
  >
{
};

template<>
struct is_service<a1z_msgs::action::MoveEndEffector_SendGoal>
  : std::true_type
{
};

template<>
struct is_service_request<a1z_msgs::action::MoveEndEffector_SendGoal_Request>
  : std::true_type
{
};

template<>
struct is_service_response<a1z_msgs::action::MoveEndEffector_SendGoal_Response>
  : std::true_type
{
};

}  // namespace rosidl_generator_traits

// Include directives for member types
// Member 'goal_id'
// already included above
// #include "unique_identifier_msgs/msg/detail/uuid__traits.hpp"

namespace a1z_msgs
{

namespace action
{

inline void to_flow_style_yaml(
  const MoveEndEffector_GetResult_Request & msg,
  std::ostream & out)
{
  out << "{";
  // member: goal_id
  {
    out << "goal_id: ";
    to_flow_style_yaml(msg.goal_id, out);
  }
  out << "}";
}  // NOLINT(readability/fn_size)

inline void to_block_style_yaml(
  const MoveEndEffector_GetResult_Request & msg,
  std::ostream & out, size_t indentation = 0)
{
  // member: goal_id
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "goal_id:\n";
    to_block_style_yaml(msg.goal_id, out, indentation + 2);
  }
}  // NOLINT(readability/fn_size)

inline std::string to_yaml(const MoveEndEffector_GetResult_Request & msg, bool use_flow_style = false)
{
  std::ostringstream out;
  if (use_flow_style) {
    to_flow_style_yaml(msg, out);
  } else {
    to_block_style_yaml(msg, out);
  }
  return out.str();
}

}  // namespace action

}  // namespace a1z_msgs

namespace rosidl_generator_traits
{

[[deprecated("use a1z_msgs::action::to_block_style_yaml() instead")]]
inline void to_yaml(
  const a1z_msgs::action::MoveEndEffector_GetResult_Request & msg,
  std::ostream & out, size_t indentation = 0)
{
  a1z_msgs::action::to_block_style_yaml(msg, out, indentation);
}

[[deprecated("use a1z_msgs::action::to_yaml() instead")]]
inline std::string to_yaml(const a1z_msgs::action::MoveEndEffector_GetResult_Request & msg)
{
  return a1z_msgs::action::to_yaml(msg);
}

template<>
inline const char * data_type<a1z_msgs::action::MoveEndEffector_GetResult_Request>()
{
  return "a1z_msgs::action::MoveEndEffector_GetResult_Request";
}

template<>
inline const char * name<a1z_msgs::action::MoveEndEffector_GetResult_Request>()
{
  return "a1z_msgs/action/MoveEndEffector_GetResult_Request";
}

template<>
struct has_fixed_size<a1z_msgs::action::MoveEndEffector_GetResult_Request>
  : std::integral_constant<bool, has_fixed_size<unique_identifier_msgs::msg::UUID>::value> {};

template<>
struct has_bounded_size<a1z_msgs::action::MoveEndEffector_GetResult_Request>
  : std::integral_constant<bool, has_bounded_size<unique_identifier_msgs::msg::UUID>::value> {};

template<>
struct is_message<a1z_msgs::action::MoveEndEffector_GetResult_Request>
  : std::true_type {};

}  // namespace rosidl_generator_traits

// Include directives for member types
// Member 'result'
// already included above
// #include "a1z_msgs/action/detail/move_end_effector__traits.hpp"

namespace a1z_msgs
{

namespace action
{

inline void to_flow_style_yaml(
  const MoveEndEffector_GetResult_Response & msg,
  std::ostream & out)
{
  out << "{";
  // member: status
  {
    out << "status: ";
    rosidl_generator_traits::value_to_yaml(msg.status, out);
    out << ", ";
  }

  // member: result
  {
    out << "result: ";
    to_flow_style_yaml(msg.result, out);
  }
  out << "}";
}  // NOLINT(readability/fn_size)

inline void to_block_style_yaml(
  const MoveEndEffector_GetResult_Response & msg,
  std::ostream & out, size_t indentation = 0)
{
  // member: status
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "status: ";
    rosidl_generator_traits::value_to_yaml(msg.status, out);
    out << "\n";
  }

  // member: result
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "result:\n";
    to_block_style_yaml(msg.result, out, indentation + 2);
  }
}  // NOLINT(readability/fn_size)

inline std::string to_yaml(const MoveEndEffector_GetResult_Response & msg, bool use_flow_style = false)
{
  std::ostringstream out;
  if (use_flow_style) {
    to_flow_style_yaml(msg, out);
  } else {
    to_block_style_yaml(msg, out);
  }
  return out.str();
}

}  // namespace action

}  // namespace a1z_msgs

namespace rosidl_generator_traits
{

[[deprecated("use a1z_msgs::action::to_block_style_yaml() instead")]]
inline void to_yaml(
  const a1z_msgs::action::MoveEndEffector_GetResult_Response & msg,
  std::ostream & out, size_t indentation = 0)
{
  a1z_msgs::action::to_block_style_yaml(msg, out, indentation);
}

[[deprecated("use a1z_msgs::action::to_yaml() instead")]]
inline std::string to_yaml(const a1z_msgs::action::MoveEndEffector_GetResult_Response & msg)
{
  return a1z_msgs::action::to_yaml(msg);
}

template<>
inline const char * data_type<a1z_msgs::action::MoveEndEffector_GetResult_Response>()
{
  return "a1z_msgs::action::MoveEndEffector_GetResult_Response";
}

template<>
inline const char * name<a1z_msgs::action::MoveEndEffector_GetResult_Response>()
{
  return "a1z_msgs/action/MoveEndEffector_GetResult_Response";
}

template<>
struct has_fixed_size<a1z_msgs::action::MoveEndEffector_GetResult_Response>
  : std::integral_constant<bool, has_fixed_size<a1z_msgs::action::MoveEndEffector_Result>::value> {};

template<>
struct has_bounded_size<a1z_msgs::action::MoveEndEffector_GetResult_Response>
  : std::integral_constant<bool, has_bounded_size<a1z_msgs::action::MoveEndEffector_Result>::value> {};

template<>
struct is_message<a1z_msgs::action::MoveEndEffector_GetResult_Response>
  : std::true_type {};

}  // namespace rosidl_generator_traits

namespace rosidl_generator_traits
{

template<>
inline const char * data_type<a1z_msgs::action::MoveEndEffector_GetResult>()
{
  return "a1z_msgs::action::MoveEndEffector_GetResult";
}

template<>
inline const char * name<a1z_msgs::action::MoveEndEffector_GetResult>()
{
  return "a1z_msgs/action/MoveEndEffector_GetResult";
}

template<>
struct has_fixed_size<a1z_msgs::action::MoveEndEffector_GetResult>
  : std::integral_constant<
    bool,
    has_fixed_size<a1z_msgs::action::MoveEndEffector_GetResult_Request>::value &&
    has_fixed_size<a1z_msgs::action::MoveEndEffector_GetResult_Response>::value
  >
{
};

template<>
struct has_bounded_size<a1z_msgs::action::MoveEndEffector_GetResult>
  : std::integral_constant<
    bool,
    has_bounded_size<a1z_msgs::action::MoveEndEffector_GetResult_Request>::value &&
    has_bounded_size<a1z_msgs::action::MoveEndEffector_GetResult_Response>::value
  >
{
};

template<>
struct is_service<a1z_msgs::action::MoveEndEffector_GetResult>
  : std::true_type
{
};

template<>
struct is_service_request<a1z_msgs::action::MoveEndEffector_GetResult_Request>
  : std::true_type
{
};

template<>
struct is_service_response<a1z_msgs::action::MoveEndEffector_GetResult_Response>
  : std::true_type
{
};

}  // namespace rosidl_generator_traits

// Include directives for member types
// Member 'goal_id'
// already included above
// #include "unique_identifier_msgs/msg/detail/uuid__traits.hpp"
// Member 'feedback'
// already included above
// #include "a1z_msgs/action/detail/move_end_effector__traits.hpp"

namespace a1z_msgs
{

namespace action
{

inline void to_flow_style_yaml(
  const MoveEndEffector_FeedbackMessage & msg,
  std::ostream & out)
{
  out << "{";
  // member: goal_id
  {
    out << "goal_id: ";
    to_flow_style_yaml(msg.goal_id, out);
    out << ", ";
  }

  // member: feedback
  {
    out << "feedback: ";
    to_flow_style_yaml(msg.feedback, out);
  }
  out << "}";
}  // NOLINT(readability/fn_size)

inline void to_block_style_yaml(
  const MoveEndEffector_FeedbackMessage & msg,
  std::ostream & out, size_t indentation = 0)
{
  // member: goal_id
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "goal_id:\n";
    to_block_style_yaml(msg.goal_id, out, indentation + 2);
  }

  // member: feedback
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "feedback:\n";
    to_block_style_yaml(msg.feedback, out, indentation + 2);
  }
}  // NOLINT(readability/fn_size)

inline std::string to_yaml(const MoveEndEffector_FeedbackMessage & msg, bool use_flow_style = false)
{
  std::ostringstream out;
  if (use_flow_style) {
    to_flow_style_yaml(msg, out);
  } else {
    to_block_style_yaml(msg, out);
  }
  return out.str();
}

}  // namespace action

}  // namespace a1z_msgs

namespace rosidl_generator_traits
{

[[deprecated("use a1z_msgs::action::to_block_style_yaml() instead")]]
inline void to_yaml(
  const a1z_msgs::action::MoveEndEffector_FeedbackMessage & msg,
  std::ostream & out, size_t indentation = 0)
{
  a1z_msgs::action::to_block_style_yaml(msg, out, indentation);
}

[[deprecated("use a1z_msgs::action::to_yaml() instead")]]
inline std::string to_yaml(const a1z_msgs::action::MoveEndEffector_FeedbackMessage & msg)
{
  return a1z_msgs::action::to_yaml(msg);
}

template<>
inline const char * data_type<a1z_msgs::action::MoveEndEffector_FeedbackMessage>()
{
  return "a1z_msgs::action::MoveEndEffector_FeedbackMessage";
}

template<>
inline const char * name<a1z_msgs::action::MoveEndEffector_FeedbackMessage>()
{
  return "a1z_msgs/action/MoveEndEffector_FeedbackMessage";
}

template<>
struct has_fixed_size<a1z_msgs::action::MoveEndEffector_FeedbackMessage>
  : std::integral_constant<bool, has_fixed_size<a1z_msgs::action::MoveEndEffector_Feedback>::value && has_fixed_size<unique_identifier_msgs::msg::UUID>::value> {};

template<>
struct has_bounded_size<a1z_msgs::action::MoveEndEffector_FeedbackMessage>
  : std::integral_constant<bool, has_bounded_size<a1z_msgs::action::MoveEndEffector_Feedback>::value && has_bounded_size<unique_identifier_msgs::msg::UUID>::value> {};

template<>
struct is_message<a1z_msgs::action::MoveEndEffector_FeedbackMessage>
  : std::true_type {};

}  // namespace rosidl_generator_traits


namespace rosidl_generator_traits
{

template<>
struct is_action<a1z_msgs::action::MoveEndEffector>
  : std::true_type
{
};

template<>
struct is_action_goal<a1z_msgs::action::MoveEndEffector_Goal>
  : std::true_type
{
};

template<>
struct is_action_result<a1z_msgs::action::MoveEndEffector_Result>
  : std::true_type
{
};

template<>
struct is_action_feedback<a1z_msgs::action::MoveEndEffector_Feedback>
  : std::true_type
{
};

}  // namespace rosidl_generator_traits


#endif  // A1Z_MSGS__ACTION__DETAIL__MOVE_END_EFFECTOR__TRAITS_HPP_
