// generated from rosidl_generator_cpp/resource/idl__builder.hpp.em
// with input from a1z_msgs:action/MoveEndEffector.idl
// generated code does not contain a copyright notice

#ifndef A1Z_MSGS__ACTION__DETAIL__MOVE_END_EFFECTOR__BUILDER_HPP_
#define A1Z_MSGS__ACTION__DETAIL__MOVE_END_EFFECTOR__BUILDER_HPP_

#include <algorithm>
#include <utility>

#include "a1z_msgs/action/detail/move_end_effector__struct.hpp"
#include "rosidl_runtime_cpp/message_initialization.hpp"


namespace a1z_msgs
{

namespace action
{

namespace builder
{

class Init_MoveEndEffector_Goal_max_target_z_m
{
public:
  explicit Init_MoveEndEffector_Goal_max_target_z_m(::a1z_msgs::action::MoveEndEffector_Goal & msg)
  : msg_(msg)
  {}
  ::a1z_msgs::action::MoveEndEffector_Goal max_target_z_m(::a1z_msgs::action::MoveEndEffector_Goal::_max_target_z_m_type arg)
  {
    msg_.max_target_z_m = std::move(arg);
    return std::move(msg_);
  }

private:
  ::a1z_msgs::action::MoveEndEffector_Goal msg_;
};

class Init_MoveEndEffector_Goal_min_target_z_m
{
public:
  explicit Init_MoveEndEffector_Goal_min_target_z_m(::a1z_msgs::action::MoveEndEffector_Goal & msg)
  : msg_(msg)
  {}
  Init_MoveEndEffector_Goal_max_target_z_m min_target_z_m(::a1z_msgs::action::MoveEndEffector_Goal::_min_target_z_m_type arg)
  {
    msg_.min_target_z_m = std::move(arg);
    return Init_MoveEndEffector_Goal_max_target_z_m(msg_);
  }

private:
  ::a1z_msgs::action::MoveEndEffector_Goal msg_;
};

class Init_MoveEndEffector_Goal_max_joint_step_rad
{
public:
  explicit Init_MoveEndEffector_Goal_max_joint_step_rad(::a1z_msgs::action::MoveEndEffector_Goal & msg)
  : msg_(msg)
  {}
  Init_MoveEndEffector_Goal_min_target_z_m max_joint_step_rad(::a1z_msgs::action::MoveEndEffector_Goal::_max_joint_step_rad_type arg)
  {
    msg_.max_joint_step_rad = std::move(arg);
    return Init_MoveEndEffector_Goal_min_target_z_m(msg_);
  }

private:
  ::a1z_msgs::action::MoveEndEffector_Goal msg_;
};

class Init_MoveEndEffector_Goal_joint_margin_rad
{
public:
  explicit Init_MoveEndEffector_Goal_joint_margin_rad(::a1z_msgs::action::MoveEndEffector_Goal & msg)
  : msg_(msg)
  {}
  Init_MoveEndEffector_Goal_max_joint_step_rad joint_margin_rad(::a1z_msgs::action::MoveEndEffector_Goal::_joint_margin_rad_type arg)
  {
    msg_.joint_margin_rad = std::move(arg);
    return Init_MoveEndEffector_Goal_max_joint_step_rad(msg_);
  }

private:
  ::a1z_msgs::action::MoveEndEffector_Goal msg_;
};

class Init_MoveEndEffector_Goal_orientation_tolerance_rad
{
public:
  explicit Init_MoveEndEffector_Goal_orientation_tolerance_rad(::a1z_msgs::action::MoveEndEffector_Goal & msg)
  : msg_(msg)
  {}
  Init_MoveEndEffector_Goal_joint_margin_rad orientation_tolerance_rad(::a1z_msgs::action::MoveEndEffector_Goal::_orientation_tolerance_rad_type arg)
  {
    msg_.orientation_tolerance_rad = std::move(arg);
    return Init_MoveEndEffector_Goal_joint_margin_rad(msg_);
  }

private:
  ::a1z_msgs::action::MoveEndEffector_Goal msg_;
};

class Init_MoveEndEffector_Goal_position_tolerance_m
{
public:
  explicit Init_MoveEndEffector_Goal_position_tolerance_m(::a1z_msgs::action::MoveEndEffector_Goal & msg)
  : msg_(msg)
  {}
  Init_MoveEndEffector_Goal_orientation_tolerance_rad position_tolerance_m(::a1z_msgs::action::MoveEndEffector_Goal::_position_tolerance_m_type arg)
  {
    msg_.position_tolerance_m = std::move(arg);
    return Init_MoveEndEffector_Goal_orientation_tolerance_rad(msg_);
  }

private:
  ::a1z_msgs::action::MoveEndEffector_Goal msg_;
};

class Init_MoveEndEffector_Goal_speed
{
public:
  explicit Init_MoveEndEffector_Goal_speed(::a1z_msgs::action::MoveEndEffector_Goal & msg)
  : msg_(msg)
  {}
  Init_MoveEndEffector_Goal_position_tolerance_m speed(::a1z_msgs::action::MoveEndEffector_Goal::_speed_type arg)
  {
    msg_.speed = std::move(arg);
    return Init_MoveEndEffector_Goal_position_tolerance_m(msg_);
  }

private:
  ::a1z_msgs::action::MoveEndEffector_Goal msg_;
};

class Init_MoveEndEffector_Goal_gripper_opening
{
public:
  explicit Init_MoveEndEffector_Goal_gripper_opening(::a1z_msgs::action::MoveEndEffector_Goal & msg)
  : msg_(msg)
  {}
  Init_MoveEndEffector_Goal_speed gripper_opening(::a1z_msgs::action::MoveEndEffector_Goal::_gripper_opening_type arg)
  {
    msg_.gripper_opening = std::move(arg);
    return Init_MoveEndEffector_Goal_speed(msg_);
  }

private:
  ::a1z_msgs::action::MoveEndEffector_Goal msg_;
};

class Init_MoveEndEffector_Goal_command_gripper
{
public:
  explicit Init_MoveEndEffector_Goal_command_gripper(::a1z_msgs::action::MoveEndEffector_Goal & msg)
  : msg_(msg)
  {}
  Init_MoveEndEffector_Goal_gripper_opening command_gripper(::a1z_msgs::action::MoveEndEffector_Goal::_command_gripper_type arg)
  {
    msg_.command_gripper = std::move(arg);
    return Init_MoveEndEffector_Goal_gripper_opening(msg_);
  }

private:
  ::a1z_msgs::action::MoveEndEffector_Goal msg_;
};

class Init_MoveEndEffector_Goal_end_effector_frame
{
public:
  explicit Init_MoveEndEffector_Goal_end_effector_frame(::a1z_msgs::action::MoveEndEffector_Goal & msg)
  : msg_(msg)
  {}
  Init_MoveEndEffector_Goal_command_gripper end_effector_frame(::a1z_msgs::action::MoveEndEffector_Goal::_end_effector_frame_type arg)
  {
    msg_.end_effector_frame = std::move(arg);
    return Init_MoveEndEffector_Goal_command_gripper(msg_);
  }

private:
  ::a1z_msgs::action::MoveEndEffector_Goal msg_;
};

class Init_MoveEndEffector_Goal_goal_pose
{
public:
  Init_MoveEndEffector_Goal_goal_pose()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_MoveEndEffector_Goal_end_effector_frame goal_pose(::a1z_msgs::action::MoveEndEffector_Goal::_goal_pose_type arg)
  {
    msg_.goal_pose = std::move(arg);
    return Init_MoveEndEffector_Goal_end_effector_frame(msg_);
  }

private:
  ::a1z_msgs::action::MoveEndEffector_Goal msg_;
};

}  // namespace builder

}  // namespace action

template<typename MessageType>
auto build();

template<>
inline
auto build<::a1z_msgs::action::MoveEndEffector_Goal>()
{
  return a1z_msgs::action::builder::Init_MoveEndEffector_Goal_goal_pose();
}

}  // namespace a1z_msgs


namespace a1z_msgs
{

namespace action
{

namespace builder
{

class Init_MoveEndEffector_Result_orientation_error_rad
{
public:
  explicit Init_MoveEndEffector_Result_orientation_error_rad(::a1z_msgs::action::MoveEndEffector_Result & msg)
  : msg_(msg)
  {}
  ::a1z_msgs::action::MoveEndEffector_Result orientation_error_rad(::a1z_msgs::action::MoveEndEffector_Result::_orientation_error_rad_type arg)
  {
    msg_.orientation_error_rad = std::move(arg);
    return std::move(msg_);
  }

private:
  ::a1z_msgs::action::MoveEndEffector_Result msg_;
};

class Init_MoveEndEffector_Result_position_error_m
{
public:
  explicit Init_MoveEndEffector_Result_position_error_m(::a1z_msgs::action::MoveEndEffector_Result & msg)
  : msg_(msg)
  {}
  Init_MoveEndEffector_Result_orientation_error_rad position_error_m(::a1z_msgs::action::MoveEndEffector_Result::_position_error_m_type arg)
  {
    msg_.position_error_m = std::move(arg);
    return Init_MoveEndEffector_Result_orientation_error_rad(msg_);
  }

private:
  ::a1z_msgs::action::MoveEndEffector_Result msg_;
};

class Init_MoveEndEffector_Result_ik_converged
{
public:
  explicit Init_MoveEndEffector_Result_ik_converged(::a1z_msgs::action::MoveEndEffector_Result & msg)
  : msg_(msg)
  {}
  Init_MoveEndEffector_Result_position_error_m ik_converged(::a1z_msgs::action::MoveEndEffector_Result::_ik_converged_type arg)
  {
    msg_.ik_converged = std::move(arg);
    return Init_MoveEndEffector_Result_position_error_m(msg_);
  }

private:
  ::a1z_msgs::action::MoveEndEffector_Result msg_;
};

class Init_MoveEndEffector_Result_final_gripper_opening
{
public:
  explicit Init_MoveEndEffector_Result_final_gripper_opening(::a1z_msgs::action::MoveEndEffector_Result & msg)
  : msg_(msg)
  {}
  Init_MoveEndEffector_Result_ik_converged final_gripper_opening(::a1z_msgs::action::MoveEndEffector_Result::_final_gripper_opening_type arg)
  {
    msg_.final_gripper_opening = std::move(arg);
    return Init_MoveEndEffector_Result_ik_converged(msg_);
  }

private:
  ::a1z_msgs::action::MoveEndEffector_Result msg_;
};

class Init_MoveEndEffector_Result_final_pose
{
public:
  explicit Init_MoveEndEffector_Result_final_pose(::a1z_msgs::action::MoveEndEffector_Result & msg)
  : msg_(msg)
  {}
  Init_MoveEndEffector_Result_final_gripper_opening final_pose(::a1z_msgs::action::MoveEndEffector_Result::_final_pose_type arg)
  {
    msg_.final_pose = std::move(arg);
    return Init_MoveEndEffector_Result_final_gripper_opening(msg_);
  }

private:
  ::a1z_msgs::action::MoveEndEffector_Result msg_;
};

class Init_MoveEndEffector_Result_final_joint_positions_rad
{
public:
  explicit Init_MoveEndEffector_Result_final_joint_positions_rad(::a1z_msgs::action::MoveEndEffector_Result & msg)
  : msg_(msg)
  {}
  Init_MoveEndEffector_Result_final_pose final_joint_positions_rad(::a1z_msgs::action::MoveEndEffector_Result::_final_joint_positions_rad_type arg)
  {
    msg_.final_joint_positions_rad = std::move(arg);
    return Init_MoveEndEffector_Result_final_pose(msg_);
  }

private:
  ::a1z_msgs::action::MoveEndEffector_Result msg_;
};

class Init_MoveEndEffector_Result_failure_reason
{
public:
  explicit Init_MoveEndEffector_Result_failure_reason(::a1z_msgs::action::MoveEndEffector_Result & msg)
  : msg_(msg)
  {}
  Init_MoveEndEffector_Result_final_joint_positions_rad failure_reason(::a1z_msgs::action::MoveEndEffector_Result::_failure_reason_type arg)
  {
    msg_.failure_reason = std::move(arg);
    return Init_MoveEndEffector_Result_final_joint_positions_rad(msg_);
  }

private:
  ::a1z_msgs::action::MoveEndEffector_Result msg_;
};

class Init_MoveEndEffector_Result_status
{
public:
  explicit Init_MoveEndEffector_Result_status(::a1z_msgs::action::MoveEndEffector_Result & msg)
  : msg_(msg)
  {}
  Init_MoveEndEffector_Result_failure_reason status(::a1z_msgs::action::MoveEndEffector_Result::_status_type arg)
  {
    msg_.status = std::move(arg);
    return Init_MoveEndEffector_Result_failure_reason(msg_);
  }

private:
  ::a1z_msgs::action::MoveEndEffector_Result msg_;
};

class Init_MoveEndEffector_Result_success
{
public:
  Init_MoveEndEffector_Result_success()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_MoveEndEffector_Result_status success(::a1z_msgs::action::MoveEndEffector_Result::_success_type arg)
  {
    msg_.success = std::move(arg);
    return Init_MoveEndEffector_Result_status(msg_);
  }

private:
  ::a1z_msgs::action::MoveEndEffector_Result msg_;
};

}  // namespace builder

}  // namespace action

template<typename MessageType>
auto build();

template<>
inline
auto build<::a1z_msgs::action::MoveEndEffector_Result>()
{
  return a1z_msgs::action::builder::Init_MoveEndEffector_Result_success();
}

}  // namespace a1z_msgs


namespace a1z_msgs
{

namespace action
{

namespace builder
{

class Init_MoveEndEffector_Feedback_message
{
public:
  explicit Init_MoveEndEffector_Feedback_message(::a1z_msgs::action::MoveEndEffector_Feedback & msg)
  : msg_(msg)
  {}
  ::a1z_msgs::action::MoveEndEffector_Feedback message(::a1z_msgs::action::MoveEndEffector_Feedback::_message_type arg)
  {
    msg_.message = std::move(arg);
    return std::move(msg_);
  }

private:
  ::a1z_msgs::action::MoveEndEffector_Feedback msg_;
};

class Init_MoveEndEffector_Feedback_stage
{
public:
  Init_MoveEndEffector_Feedback_stage()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_MoveEndEffector_Feedback_message stage(::a1z_msgs::action::MoveEndEffector_Feedback::_stage_type arg)
  {
    msg_.stage = std::move(arg);
    return Init_MoveEndEffector_Feedback_message(msg_);
  }

private:
  ::a1z_msgs::action::MoveEndEffector_Feedback msg_;
};

}  // namespace builder

}  // namespace action

template<typename MessageType>
auto build();

template<>
inline
auto build<::a1z_msgs::action::MoveEndEffector_Feedback>()
{
  return a1z_msgs::action::builder::Init_MoveEndEffector_Feedback_stage();
}

}  // namespace a1z_msgs


namespace a1z_msgs
{

namespace action
{

namespace builder
{

class Init_MoveEndEffector_SendGoal_Request_goal
{
public:
  explicit Init_MoveEndEffector_SendGoal_Request_goal(::a1z_msgs::action::MoveEndEffector_SendGoal_Request & msg)
  : msg_(msg)
  {}
  ::a1z_msgs::action::MoveEndEffector_SendGoal_Request goal(::a1z_msgs::action::MoveEndEffector_SendGoal_Request::_goal_type arg)
  {
    msg_.goal = std::move(arg);
    return std::move(msg_);
  }

private:
  ::a1z_msgs::action::MoveEndEffector_SendGoal_Request msg_;
};

class Init_MoveEndEffector_SendGoal_Request_goal_id
{
public:
  Init_MoveEndEffector_SendGoal_Request_goal_id()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_MoveEndEffector_SendGoal_Request_goal goal_id(::a1z_msgs::action::MoveEndEffector_SendGoal_Request::_goal_id_type arg)
  {
    msg_.goal_id = std::move(arg);
    return Init_MoveEndEffector_SendGoal_Request_goal(msg_);
  }

private:
  ::a1z_msgs::action::MoveEndEffector_SendGoal_Request msg_;
};

}  // namespace builder

}  // namespace action

template<typename MessageType>
auto build();

template<>
inline
auto build<::a1z_msgs::action::MoveEndEffector_SendGoal_Request>()
{
  return a1z_msgs::action::builder::Init_MoveEndEffector_SendGoal_Request_goal_id();
}

}  // namespace a1z_msgs


namespace a1z_msgs
{

namespace action
{

namespace builder
{

class Init_MoveEndEffector_SendGoal_Response_stamp
{
public:
  explicit Init_MoveEndEffector_SendGoal_Response_stamp(::a1z_msgs::action::MoveEndEffector_SendGoal_Response & msg)
  : msg_(msg)
  {}
  ::a1z_msgs::action::MoveEndEffector_SendGoal_Response stamp(::a1z_msgs::action::MoveEndEffector_SendGoal_Response::_stamp_type arg)
  {
    msg_.stamp = std::move(arg);
    return std::move(msg_);
  }

private:
  ::a1z_msgs::action::MoveEndEffector_SendGoal_Response msg_;
};

class Init_MoveEndEffector_SendGoal_Response_accepted
{
public:
  Init_MoveEndEffector_SendGoal_Response_accepted()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_MoveEndEffector_SendGoal_Response_stamp accepted(::a1z_msgs::action::MoveEndEffector_SendGoal_Response::_accepted_type arg)
  {
    msg_.accepted = std::move(arg);
    return Init_MoveEndEffector_SendGoal_Response_stamp(msg_);
  }

private:
  ::a1z_msgs::action::MoveEndEffector_SendGoal_Response msg_;
};

}  // namespace builder

}  // namespace action

template<typename MessageType>
auto build();

template<>
inline
auto build<::a1z_msgs::action::MoveEndEffector_SendGoal_Response>()
{
  return a1z_msgs::action::builder::Init_MoveEndEffector_SendGoal_Response_accepted();
}

}  // namespace a1z_msgs


namespace a1z_msgs
{

namespace action
{

namespace builder
{

class Init_MoveEndEffector_GetResult_Request_goal_id
{
public:
  Init_MoveEndEffector_GetResult_Request_goal_id()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  ::a1z_msgs::action::MoveEndEffector_GetResult_Request goal_id(::a1z_msgs::action::MoveEndEffector_GetResult_Request::_goal_id_type arg)
  {
    msg_.goal_id = std::move(arg);
    return std::move(msg_);
  }

private:
  ::a1z_msgs::action::MoveEndEffector_GetResult_Request msg_;
};

}  // namespace builder

}  // namespace action

template<typename MessageType>
auto build();

template<>
inline
auto build<::a1z_msgs::action::MoveEndEffector_GetResult_Request>()
{
  return a1z_msgs::action::builder::Init_MoveEndEffector_GetResult_Request_goal_id();
}

}  // namespace a1z_msgs


namespace a1z_msgs
{

namespace action
{

namespace builder
{

class Init_MoveEndEffector_GetResult_Response_result
{
public:
  explicit Init_MoveEndEffector_GetResult_Response_result(::a1z_msgs::action::MoveEndEffector_GetResult_Response & msg)
  : msg_(msg)
  {}
  ::a1z_msgs::action::MoveEndEffector_GetResult_Response result(::a1z_msgs::action::MoveEndEffector_GetResult_Response::_result_type arg)
  {
    msg_.result = std::move(arg);
    return std::move(msg_);
  }

private:
  ::a1z_msgs::action::MoveEndEffector_GetResult_Response msg_;
};

class Init_MoveEndEffector_GetResult_Response_status
{
public:
  Init_MoveEndEffector_GetResult_Response_status()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_MoveEndEffector_GetResult_Response_result status(::a1z_msgs::action::MoveEndEffector_GetResult_Response::_status_type arg)
  {
    msg_.status = std::move(arg);
    return Init_MoveEndEffector_GetResult_Response_result(msg_);
  }

private:
  ::a1z_msgs::action::MoveEndEffector_GetResult_Response msg_;
};

}  // namespace builder

}  // namespace action

template<typename MessageType>
auto build();

template<>
inline
auto build<::a1z_msgs::action::MoveEndEffector_GetResult_Response>()
{
  return a1z_msgs::action::builder::Init_MoveEndEffector_GetResult_Response_status();
}

}  // namespace a1z_msgs


namespace a1z_msgs
{

namespace action
{

namespace builder
{

class Init_MoveEndEffector_FeedbackMessage_feedback
{
public:
  explicit Init_MoveEndEffector_FeedbackMessage_feedback(::a1z_msgs::action::MoveEndEffector_FeedbackMessage & msg)
  : msg_(msg)
  {}
  ::a1z_msgs::action::MoveEndEffector_FeedbackMessage feedback(::a1z_msgs::action::MoveEndEffector_FeedbackMessage::_feedback_type arg)
  {
    msg_.feedback = std::move(arg);
    return std::move(msg_);
  }

private:
  ::a1z_msgs::action::MoveEndEffector_FeedbackMessage msg_;
};

class Init_MoveEndEffector_FeedbackMessage_goal_id
{
public:
  Init_MoveEndEffector_FeedbackMessage_goal_id()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_MoveEndEffector_FeedbackMessage_feedback goal_id(::a1z_msgs::action::MoveEndEffector_FeedbackMessage::_goal_id_type arg)
  {
    msg_.goal_id = std::move(arg);
    return Init_MoveEndEffector_FeedbackMessage_feedback(msg_);
  }

private:
  ::a1z_msgs::action::MoveEndEffector_FeedbackMessage msg_;
};

}  // namespace builder

}  // namespace action

template<typename MessageType>
auto build();

template<>
inline
auto build<::a1z_msgs::action::MoveEndEffector_FeedbackMessage>()
{
  return a1z_msgs::action::builder::Init_MoveEndEffector_FeedbackMessage_goal_id();
}

}  // namespace a1z_msgs

#endif  // A1Z_MSGS__ACTION__DETAIL__MOVE_END_EFFECTOR__BUILDER_HPP_
