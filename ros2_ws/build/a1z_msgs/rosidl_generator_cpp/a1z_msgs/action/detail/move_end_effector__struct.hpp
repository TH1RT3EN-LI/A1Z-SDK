// generated from rosidl_generator_cpp/resource/idl__struct.hpp.em
// with input from a1z_msgs:action/MoveEndEffector.idl
// generated code does not contain a copyright notice

#ifndef A1Z_MSGS__ACTION__DETAIL__MOVE_END_EFFECTOR__STRUCT_HPP_
#define A1Z_MSGS__ACTION__DETAIL__MOVE_END_EFFECTOR__STRUCT_HPP_

#include <algorithm>
#include <array>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

#include "rosidl_runtime_cpp/bounded_vector.hpp"
#include "rosidl_runtime_cpp/message_initialization.hpp"


// Include directives for member types
// Member 'goal_pose'
#include "geometry_msgs/msg/detail/pose_stamped__struct.hpp"

#ifndef _WIN32
# define DEPRECATED__a1z_msgs__action__MoveEndEffector_Goal __attribute__((deprecated))
#else
# define DEPRECATED__a1z_msgs__action__MoveEndEffector_Goal __declspec(deprecated)
#endif

namespace a1z_msgs
{

namespace action
{

// message struct
template<class ContainerAllocator>
struct MoveEndEffector_Goal_
{
  using Type = MoveEndEffector_Goal_<ContainerAllocator>;

  explicit MoveEndEffector_Goal_(rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : goal_pose(_init)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->end_effector_frame = "";
      this->command_gripper = false;
      this->gripper_opening = 0.0f;
      this->speed = 0.0f;
      this->position_tolerance_m = 0.0f;
      this->orientation_tolerance_rad = 0.0f;
      this->joint_margin_rad = 0.0f;
      this->max_joint_step_rad = 0.0f;
      this->min_target_z_m = 0.0f;
      this->max_target_z_m = 0.0f;
    }
  }

  explicit MoveEndEffector_Goal_(const ContainerAllocator & _alloc, rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : goal_pose(_alloc, _init),
    end_effector_frame(_alloc)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->end_effector_frame = "";
      this->command_gripper = false;
      this->gripper_opening = 0.0f;
      this->speed = 0.0f;
      this->position_tolerance_m = 0.0f;
      this->orientation_tolerance_rad = 0.0f;
      this->joint_margin_rad = 0.0f;
      this->max_joint_step_rad = 0.0f;
      this->min_target_z_m = 0.0f;
      this->max_target_z_m = 0.0f;
    }
  }

  // field types and members
  using _goal_pose_type =
    geometry_msgs::msg::PoseStamped_<ContainerAllocator>;
  _goal_pose_type goal_pose;
  using _end_effector_frame_type =
    std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>>;
  _end_effector_frame_type end_effector_frame;
  using _command_gripper_type =
    bool;
  _command_gripper_type command_gripper;
  using _gripper_opening_type =
    float;
  _gripper_opening_type gripper_opening;
  using _speed_type =
    float;
  _speed_type speed;
  using _position_tolerance_m_type =
    float;
  _position_tolerance_m_type position_tolerance_m;
  using _orientation_tolerance_rad_type =
    float;
  _orientation_tolerance_rad_type orientation_tolerance_rad;
  using _joint_margin_rad_type =
    float;
  _joint_margin_rad_type joint_margin_rad;
  using _max_joint_step_rad_type =
    float;
  _max_joint_step_rad_type max_joint_step_rad;
  using _min_target_z_m_type =
    float;
  _min_target_z_m_type min_target_z_m;
  using _max_target_z_m_type =
    float;
  _max_target_z_m_type max_target_z_m;

  // setters for named parameter idiom
  Type & set__goal_pose(
    const geometry_msgs::msg::PoseStamped_<ContainerAllocator> & _arg)
  {
    this->goal_pose = _arg;
    return *this;
  }
  Type & set__end_effector_frame(
    const std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>> & _arg)
  {
    this->end_effector_frame = _arg;
    return *this;
  }
  Type & set__command_gripper(
    const bool & _arg)
  {
    this->command_gripper = _arg;
    return *this;
  }
  Type & set__gripper_opening(
    const float & _arg)
  {
    this->gripper_opening = _arg;
    return *this;
  }
  Type & set__speed(
    const float & _arg)
  {
    this->speed = _arg;
    return *this;
  }
  Type & set__position_tolerance_m(
    const float & _arg)
  {
    this->position_tolerance_m = _arg;
    return *this;
  }
  Type & set__orientation_tolerance_rad(
    const float & _arg)
  {
    this->orientation_tolerance_rad = _arg;
    return *this;
  }
  Type & set__joint_margin_rad(
    const float & _arg)
  {
    this->joint_margin_rad = _arg;
    return *this;
  }
  Type & set__max_joint_step_rad(
    const float & _arg)
  {
    this->max_joint_step_rad = _arg;
    return *this;
  }
  Type & set__min_target_z_m(
    const float & _arg)
  {
    this->min_target_z_m = _arg;
    return *this;
  }
  Type & set__max_target_z_m(
    const float & _arg)
  {
    this->max_target_z_m = _arg;
    return *this;
  }

  // constant declarations

  // pointer types
  using RawPtr =
    a1z_msgs::action::MoveEndEffector_Goal_<ContainerAllocator> *;
  using ConstRawPtr =
    const a1z_msgs::action::MoveEndEffector_Goal_<ContainerAllocator> *;
  using SharedPtr =
    std::shared_ptr<a1z_msgs::action::MoveEndEffector_Goal_<ContainerAllocator>>;
  using ConstSharedPtr =
    std::shared_ptr<a1z_msgs::action::MoveEndEffector_Goal_<ContainerAllocator> const>;

  template<typename Deleter = std::default_delete<
      a1z_msgs::action::MoveEndEffector_Goal_<ContainerAllocator>>>
  using UniquePtrWithDeleter =
    std::unique_ptr<a1z_msgs::action::MoveEndEffector_Goal_<ContainerAllocator>, Deleter>;

  using UniquePtr = UniquePtrWithDeleter<>;

  template<typename Deleter = std::default_delete<
      a1z_msgs::action::MoveEndEffector_Goal_<ContainerAllocator>>>
  using ConstUniquePtrWithDeleter =
    std::unique_ptr<a1z_msgs::action::MoveEndEffector_Goal_<ContainerAllocator> const, Deleter>;
  using ConstUniquePtr = ConstUniquePtrWithDeleter<>;

  using WeakPtr =
    std::weak_ptr<a1z_msgs::action::MoveEndEffector_Goal_<ContainerAllocator>>;
  using ConstWeakPtr =
    std::weak_ptr<a1z_msgs::action::MoveEndEffector_Goal_<ContainerAllocator> const>;

  // pointer types similar to ROS 1, use SharedPtr / ConstSharedPtr instead
  // NOTE: Can't use 'using' here because GNU C++ can't parse attributes properly
  typedef DEPRECATED__a1z_msgs__action__MoveEndEffector_Goal
    std::shared_ptr<a1z_msgs::action::MoveEndEffector_Goal_<ContainerAllocator>>
    Ptr;
  typedef DEPRECATED__a1z_msgs__action__MoveEndEffector_Goal
    std::shared_ptr<a1z_msgs::action::MoveEndEffector_Goal_<ContainerAllocator> const>
    ConstPtr;

  // comparison operators
  bool operator==(const MoveEndEffector_Goal_ & other) const
  {
    if (this->goal_pose != other.goal_pose) {
      return false;
    }
    if (this->end_effector_frame != other.end_effector_frame) {
      return false;
    }
    if (this->command_gripper != other.command_gripper) {
      return false;
    }
    if (this->gripper_opening != other.gripper_opening) {
      return false;
    }
    if (this->speed != other.speed) {
      return false;
    }
    if (this->position_tolerance_m != other.position_tolerance_m) {
      return false;
    }
    if (this->orientation_tolerance_rad != other.orientation_tolerance_rad) {
      return false;
    }
    if (this->joint_margin_rad != other.joint_margin_rad) {
      return false;
    }
    if (this->max_joint_step_rad != other.max_joint_step_rad) {
      return false;
    }
    if (this->min_target_z_m != other.min_target_z_m) {
      return false;
    }
    if (this->max_target_z_m != other.max_target_z_m) {
      return false;
    }
    return true;
  }
  bool operator!=(const MoveEndEffector_Goal_ & other) const
  {
    return !this->operator==(other);
  }
};  // struct MoveEndEffector_Goal_

// alias to use template instance with default allocator
using MoveEndEffector_Goal =
  a1z_msgs::action::MoveEndEffector_Goal_<std::allocator<void>>;

// constant definitions

}  // namespace action

}  // namespace a1z_msgs


// Include directives for member types
// Member 'final_pose'
// already included above
// #include "geometry_msgs/msg/detail/pose_stamped__struct.hpp"

#ifndef _WIN32
# define DEPRECATED__a1z_msgs__action__MoveEndEffector_Result __attribute__((deprecated))
#else
# define DEPRECATED__a1z_msgs__action__MoveEndEffector_Result __declspec(deprecated)
#endif

namespace a1z_msgs
{

namespace action
{

// message struct
template<class ContainerAllocator>
struct MoveEndEffector_Result_
{
  using Type = MoveEndEffector_Result_<ContainerAllocator>;

  explicit MoveEndEffector_Result_(rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : final_pose(_init)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->success = false;
      this->status = "";
      this->failure_reason = "";
      this->final_gripper_opening = 0.0f;
      this->ik_converged = false;
      this->position_error_m = 0.0f;
      this->orientation_error_rad = 0.0f;
    }
  }

  explicit MoveEndEffector_Result_(const ContainerAllocator & _alloc, rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : status(_alloc),
    failure_reason(_alloc),
    final_pose(_alloc, _init)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->success = false;
      this->status = "";
      this->failure_reason = "";
      this->final_gripper_opening = 0.0f;
      this->ik_converged = false;
      this->position_error_m = 0.0f;
      this->orientation_error_rad = 0.0f;
    }
  }

  // field types and members
  using _success_type =
    bool;
  _success_type success;
  using _status_type =
    std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>>;
  _status_type status;
  using _failure_reason_type =
    std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>>;
  _failure_reason_type failure_reason;
  using _final_joint_positions_rad_type =
    std::vector<double, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<double>>;
  _final_joint_positions_rad_type final_joint_positions_rad;
  using _final_pose_type =
    geometry_msgs::msg::PoseStamped_<ContainerAllocator>;
  _final_pose_type final_pose;
  using _final_gripper_opening_type =
    float;
  _final_gripper_opening_type final_gripper_opening;
  using _ik_converged_type =
    bool;
  _ik_converged_type ik_converged;
  using _position_error_m_type =
    float;
  _position_error_m_type position_error_m;
  using _orientation_error_rad_type =
    float;
  _orientation_error_rad_type orientation_error_rad;

  // setters for named parameter idiom
  Type & set__success(
    const bool & _arg)
  {
    this->success = _arg;
    return *this;
  }
  Type & set__status(
    const std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>> & _arg)
  {
    this->status = _arg;
    return *this;
  }
  Type & set__failure_reason(
    const std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>> & _arg)
  {
    this->failure_reason = _arg;
    return *this;
  }
  Type & set__final_joint_positions_rad(
    const std::vector<double, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<double>> & _arg)
  {
    this->final_joint_positions_rad = _arg;
    return *this;
  }
  Type & set__final_pose(
    const geometry_msgs::msg::PoseStamped_<ContainerAllocator> & _arg)
  {
    this->final_pose = _arg;
    return *this;
  }
  Type & set__final_gripper_opening(
    const float & _arg)
  {
    this->final_gripper_opening = _arg;
    return *this;
  }
  Type & set__ik_converged(
    const bool & _arg)
  {
    this->ik_converged = _arg;
    return *this;
  }
  Type & set__position_error_m(
    const float & _arg)
  {
    this->position_error_m = _arg;
    return *this;
  }
  Type & set__orientation_error_rad(
    const float & _arg)
  {
    this->orientation_error_rad = _arg;
    return *this;
  }

  // constant declarations

  // pointer types
  using RawPtr =
    a1z_msgs::action::MoveEndEffector_Result_<ContainerAllocator> *;
  using ConstRawPtr =
    const a1z_msgs::action::MoveEndEffector_Result_<ContainerAllocator> *;
  using SharedPtr =
    std::shared_ptr<a1z_msgs::action::MoveEndEffector_Result_<ContainerAllocator>>;
  using ConstSharedPtr =
    std::shared_ptr<a1z_msgs::action::MoveEndEffector_Result_<ContainerAllocator> const>;

  template<typename Deleter = std::default_delete<
      a1z_msgs::action::MoveEndEffector_Result_<ContainerAllocator>>>
  using UniquePtrWithDeleter =
    std::unique_ptr<a1z_msgs::action::MoveEndEffector_Result_<ContainerAllocator>, Deleter>;

  using UniquePtr = UniquePtrWithDeleter<>;

  template<typename Deleter = std::default_delete<
      a1z_msgs::action::MoveEndEffector_Result_<ContainerAllocator>>>
  using ConstUniquePtrWithDeleter =
    std::unique_ptr<a1z_msgs::action::MoveEndEffector_Result_<ContainerAllocator> const, Deleter>;
  using ConstUniquePtr = ConstUniquePtrWithDeleter<>;

  using WeakPtr =
    std::weak_ptr<a1z_msgs::action::MoveEndEffector_Result_<ContainerAllocator>>;
  using ConstWeakPtr =
    std::weak_ptr<a1z_msgs::action::MoveEndEffector_Result_<ContainerAllocator> const>;

  // pointer types similar to ROS 1, use SharedPtr / ConstSharedPtr instead
  // NOTE: Can't use 'using' here because GNU C++ can't parse attributes properly
  typedef DEPRECATED__a1z_msgs__action__MoveEndEffector_Result
    std::shared_ptr<a1z_msgs::action::MoveEndEffector_Result_<ContainerAllocator>>
    Ptr;
  typedef DEPRECATED__a1z_msgs__action__MoveEndEffector_Result
    std::shared_ptr<a1z_msgs::action::MoveEndEffector_Result_<ContainerAllocator> const>
    ConstPtr;

  // comparison operators
  bool operator==(const MoveEndEffector_Result_ & other) const
  {
    if (this->success != other.success) {
      return false;
    }
    if (this->status != other.status) {
      return false;
    }
    if (this->failure_reason != other.failure_reason) {
      return false;
    }
    if (this->final_joint_positions_rad != other.final_joint_positions_rad) {
      return false;
    }
    if (this->final_pose != other.final_pose) {
      return false;
    }
    if (this->final_gripper_opening != other.final_gripper_opening) {
      return false;
    }
    if (this->ik_converged != other.ik_converged) {
      return false;
    }
    if (this->position_error_m != other.position_error_m) {
      return false;
    }
    if (this->orientation_error_rad != other.orientation_error_rad) {
      return false;
    }
    return true;
  }
  bool operator!=(const MoveEndEffector_Result_ & other) const
  {
    return !this->operator==(other);
  }
};  // struct MoveEndEffector_Result_

// alias to use template instance with default allocator
using MoveEndEffector_Result =
  a1z_msgs::action::MoveEndEffector_Result_<std::allocator<void>>;

// constant definitions

}  // namespace action

}  // namespace a1z_msgs


#ifndef _WIN32
# define DEPRECATED__a1z_msgs__action__MoveEndEffector_Feedback __attribute__((deprecated))
#else
# define DEPRECATED__a1z_msgs__action__MoveEndEffector_Feedback __declspec(deprecated)
#endif

namespace a1z_msgs
{

namespace action
{

// message struct
template<class ContainerAllocator>
struct MoveEndEffector_Feedback_
{
  using Type = MoveEndEffector_Feedback_<ContainerAllocator>;

  explicit MoveEndEffector_Feedback_(rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->stage = "";
      this->message = "";
    }
  }

  explicit MoveEndEffector_Feedback_(const ContainerAllocator & _alloc, rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : stage(_alloc),
    message(_alloc)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->stage = "";
      this->message = "";
    }
  }

  // field types and members
  using _stage_type =
    std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>>;
  _stage_type stage;
  using _message_type =
    std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>>;
  _message_type message;

  // setters for named parameter idiom
  Type & set__stage(
    const std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>> & _arg)
  {
    this->stage = _arg;
    return *this;
  }
  Type & set__message(
    const std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>> & _arg)
  {
    this->message = _arg;
    return *this;
  }

  // constant declarations

  // pointer types
  using RawPtr =
    a1z_msgs::action::MoveEndEffector_Feedback_<ContainerAllocator> *;
  using ConstRawPtr =
    const a1z_msgs::action::MoveEndEffector_Feedback_<ContainerAllocator> *;
  using SharedPtr =
    std::shared_ptr<a1z_msgs::action::MoveEndEffector_Feedback_<ContainerAllocator>>;
  using ConstSharedPtr =
    std::shared_ptr<a1z_msgs::action::MoveEndEffector_Feedback_<ContainerAllocator> const>;

  template<typename Deleter = std::default_delete<
      a1z_msgs::action::MoveEndEffector_Feedback_<ContainerAllocator>>>
  using UniquePtrWithDeleter =
    std::unique_ptr<a1z_msgs::action::MoveEndEffector_Feedback_<ContainerAllocator>, Deleter>;

  using UniquePtr = UniquePtrWithDeleter<>;

  template<typename Deleter = std::default_delete<
      a1z_msgs::action::MoveEndEffector_Feedback_<ContainerAllocator>>>
  using ConstUniquePtrWithDeleter =
    std::unique_ptr<a1z_msgs::action::MoveEndEffector_Feedback_<ContainerAllocator> const, Deleter>;
  using ConstUniquePtr = ConstUniquePtrWithDeleter<>;

  using WeakPtr =
    std::weak_ptr<a1z_msgs::action::MoveEndEffector_Feedback_<ContainerAllocator>>;
  using ConstWeakPtr =
    std::weak_ptr<a1z_msgs::action::MoveEndEffector_Feedback_<ContainerAllocator> const>;

  // pointer types similar to ROS 1, use SharedPtr / ConstSharedPtr instead
  // NOTE: Can't use 'using' here because GNU C++ can't parse attributes properly
  typedef DEPRECATED__a1z_msgs__action__MoveEndEffector_Feedback
    std::shared_ptr<a1z_msgs::action::MoveEndEffector_Feedback_<ContainerAllocator>>
    Ptr;
  typedef DEPRECATED__a1z_msgs__action__MoveEndEffector_Feedback
    std::shared_ptr<a1z_msgs::action::MoveEndEffector_Feedback_<ContainerAllocator> const>
    ConstPtr;

  // comparison operators
  bool operator==(const MoveEndEffector_Feedback_ & other) const
  {
    if (this->stage != other.stage) {
      return false;
    }
    if (this->message != other.message) {
      return false;
    }
    return true;
  }
  bool operator!=(const MoveEndEffector_Feedback_ & other) const
  {
    return !this->operator==(other);
  }
};  // struct MoveEndEffector_Feedback_

// alias to use template instance with default allocator
using MoveEndEffector_Feedback =
  a1z_msgs::action::MoveEndEffector_Feedback_<std::allocator<void>>;

// constant definitions

}  // namespace action

}  // namespace a1z_msgs


// Include directives for member types
// Member 'goal_id'
#include "unique_identifier_msgs/msg/detail/uuid__struct.hpp"
// Member 'goal'
#include "a1z_msgs/action/detail/move_end_effector__struct.hpp"

#ifndef _WIN32
# define DEPRECATED__a1z_msgs__action__MoveEndEffector_SendGoal_Request __attribute__((deprecated))
#else
# define DEPRECATED__a1z_msgs__action__MoveEndEffector_SendGoal_Request __declspec(deprecated)
#endif

namespace a1z_msgs
{

namespace action
{

// message struct
template<class ContainerAllocator>
struct MoveEndEffector_SendGoal_Request_
{
  using Type = MoveEndEffector_SendGoal_Request_<ContainerAllocator>;

  explicit MoveEndEffector_SendGoal_Request_(rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : goal_id(_init),
    goal(_init)
  {
    (void)_init;
  }

  explicit MoveEndEffector_SendGoal_Request_(const ContainerAllocator & _alloc, rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : goal_id(_alloc, _init),
    goal(_alloc, _init)
  {
    (void)_init;
  }

  // field types and members
  using _goal_id_type =
    unique_identifier_msgs::msg::UUID_<ContainerAllocator>;
  _goal_id_type goal_id;
  using _goal_type =
    a1z_msgs::action::MoveEndEffector_Goal_<ContainerAllocator>;
  _goal_type goal;

  // setters for named parameter idiom
  Type & set__goal_id(
    const unique_identifier_msgs::msg::UUID_<ContainerAllocator> & _arg)
  {
    this->goal_id = _arg;
    return *this;
  }
  Type & set__goal(
    const a1z_msgs::action::MoveEndEffector_Goal_<ContainerAllocator> & _arg)
  {
    this->goal = _arg;
    return *this;
  }

  // constant declarations

  // pointer types
  using RawPtr =
    a1z_msgs::action::MoveEndEffector_SendGoal_Request_<ContainerAllocator> *;
  using ConstRawPtr =
    const a1z_msgs::action::MoveEndEffector_SendGoal_Request_<ContainerAllocator> *;
  using SharedPtr =
    std::shared_ptr<a1z_msgs::action::MoveEndEffector_SendGoal_Request_<ContainerAllocator>>;
  using ConstSharedPtr =
    std::shared_ptr<a1z_msgs::action::MoveEndEffector_SendGoal_Request_<ContainerAllocator> const>;

  template<typename Deleter = std::default_delete<
      a1z_msgs::action::MoveEndEffector_SendGoal_Request_<ContainerAllocator>>>
  using UniquePtrWithDeleter =
    std::unique_ptr<a1z_msgs::action::MoveEndEffector_SendGoal_Request_<ContainerAllocator>, Deleter>;

  using UniquePtr = UniquePtrWithDeleter<>;

  template<typename Deleter = std::default_delete<
      a1z_msgs::action::MoveEndEffector_SendGoal_Request_<ContainerAllocator>>>
  using ConstUniquePtrWithDeleter =
    std::unique_ptr<a1z_msgs::action::MoveEndEffector_SendGoal_Request_<ContainerAllocator> const, Deleter>;
  using ConstUniquePtr = ConstUniquePtrWithDeleter<>;

  using WeakPtr =
    std::weak_ptr<a1z_msgs::action::MoveEndEffector_SendGoal_Request_<ContainerAllocator>>;
  using ConstWeakPtr =
    std::weak_ptr<a1z_msgs::action::MoveEndEffector_SendGoal_Request_<ContainerAllocator> const>;

  // pointer types similar to ROS 1, use SharedPtr / ConstSharedPtr instead
  // NOTE: Can't use 'using' here because GNU C++ can't parse attributes properly
  typedef DEPRECATED__a1z_msgs__action__MoveEndEffector_SendGoal_Request
    std::shared_ptr<a1z_msgs::action::MoveEndEffector_SendGoal_Request_<ContainerAllocator>>
    Ptr;
  typedef DEPRECATED__a1z_msgs__action__MoveEndEffector_SendGoal_Request
    std::shared_ptr<a1z_msgs::action::MoveEndEffector_SendGoal_Request_<ContainerAllocator> const>
    ConstPtr;

  // comparison operators
  bool operator==(const MoveEndEffector_SendGoal_Request_ & other) const
  {
    if (this->goal_id != other.goal_id) {
      return false;
    }
    if (this->goal != other.goal) {
      return false;
    }
    return true;
  }
  bool operator!=(const MoveEndEffector_SendGoal_Request_ & other) const
  {
    return !this->operator==(other);
  }
};  // struct MoveEndEffector_SendGoal_Request_

// alias to use template instance with default allocator
using MoveEndEffector_SendGoal_Request =
  a1z_msgs::action::MoveEndEffector_SendGoal_Request_<std::allocator<void>>;

// constant definitions

}  // namespace action

}  // namespace a1z_msgs


// Include directives for member types
// Member 'stamp'
#include "builtin_interfaces/msg/detail/time__struct.hpp"

#ifndef _WIN32
# define DEPRECATED__a1z_msgs__action__MoveEndEffector_SendGoal_Response __attribute__((deprecated))
#else
# define DEPRECATED__a1z_msgs__action__MoveEndEffector_SendGoal_Response __declspec(deprecated)
#endif

namespace a1z_msgs
{

namespace action
{

// message struct
template<class ContainerAllocator>
struct MoveEndEffector_SendGoal_Response_
{
  using Type = MoveEndEffector_SendGoal_Response_<ContainerAllocator>;

  explicit MoveEndEffector_SendGoal_Response_(rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : stamp(_init)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->accepted = false;
    }
  }

  explicit MoveEndEffector_SendGoal_Response_(const ContainerAllocator & _alloc, rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : stamp(_alloc, _init)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->accepted = false;
    }
  }

  // field types and members
  using _accepted_type =
    bool;
  _accepted_type accepted;
  using _stamp_type =
    builtin_interfaces::msg::Time_<ContainerAllocator>;
  _stamp_type stamp;

  // setters for named parameter idiom
  Type & set__accepted(
    const bool & _arg)
  {
    this->accepted = _arg;
    return *this;
  }
  Type & set__stamp(
    const builtin_interfaces::msg::Time_<ContainerAllocator> & _arg)
  {
    this->stamp = _arg;
    return *this;
  }

  // constant declarations

  // pointer types
  using RawPtr =
    a1z_msgs::action::MoveEndEffector_SendGoal_Response_<ContainerAllocator> *;
  using ConstRawPtr =
    const a1z_msgs::action::MoveEndEffector_SendGoal_Response_<ContainerAllocator> *;
  using SharedPtr =
    std::shared_ptr<a1z_msgs::action::MoveEndEffector_SendGoal_Response_<ContainerAllocator>>;
  using ConstSharedPtr =
    std::shared_ptr<a1z_msgs::action::MoveEndEffector_SendGoal_Response_<ContainerAllocator> const>;

  template<typename Deleter = std::default_delete<
      a1z_msgs::action::MoveEndEffector_SendGoal_Response_<ContainerAllocator>>>
  using UniquePtrWithDeleter =
    std::unique_ptr<a1z_msgs::action::MoveEndEffector_SendGoal_Response_<ContainerAllocator>, Deleter>;

  using UniquePtr = UniquePtrWithDeleter<>;

  template<typename Deleter = std::default_delete<
      a1z_msgs::action::MoveEndEffector_SendGoal_Response_<ContainerAllocator>>>
  using ConstUniquePtrWithDeleter =
    std::unique_ptr<a1z_msgs::action::MoveEndEffector_SendGoal_Response_<ContainerAllocator> const, Deleter>;
  using ConstUniquePtr = ConstUniquePtrWithDeleter<>;

  using WeakPtr =
    std::weak_ptr<a1z_msgs::action::MoveEndEffector_SendGoal_Response_<ContainerAllocator>>;
  using ConstWeakPtr =
    std::weak_ptr<a1z_msgs::action::MoveEndEffector_SendGoal_Response_<ContainerAllocator> const>;

  // pointer types similar to ROS 1, use SharedPtr / ConstSharedPtr instead
  // NOTE: Can't use 'using' here because GNU C++ can't parse attributes properly
  typedef DEPRECATED__a1z_msgs__action__MoveEndEffector_SendGoal_Response
    std::shared_ptr<a1z_msgs::action::MoveEndEffector_SendGoal_Response_<ContainerAllocator>>
    Ptr;
  typedef DEPRECATED__a1z_msgs__action__MoveEndEffector_SendGoal_Response
    std::shared_ptr<a1z_msgs::action::MoveEndEffector_SendGoal_Response_<ContainerAllocator> const>
    ConstPtr;

  // comparison operators
  bool operator==(const MoveEndEffector_SendGoal_Response_ & other) const
  {
    if (this->accepted != other.accepted) {
      return false;
    }
    if (this->stamp != other.stamp) {
      return false;
    }
    return true;
  }
  bool operator!=(const MoveEndEffector_SendGoal_Response_ & other) const
  {
    return !this->operator==(other);
  }
};  // struct MoveEndEffector_SendGoal_Response_

// alias to use template instance with default allocator
using MoveEndEffector_SendGoal_Response =
  a1z_msgs::action::MoveEndEffector_SendGoal_Response_<std::allocator<void>>;

// constant definitions

}  // namespace action

}  // namespace a1z_msgs

namespace a1z_msgs
{

namespace action
{

struct MoveEndEffector_SendGoal
{
  using Request = a1z_msgs::action::MoveEndEffector_SendGoal_Request;
  using Response = a1z_msgs::action::MoveEndEffector_SendGoal_Response;
};

}  // namespace action

}  // namespace a1z_msgs


// Include directives for member types
// Member 'goal_id'
// already included above
// #include "unique_identifier_msgs/msg/detail/uuid__struct.hpp"

#ifndef _WIN32
# define DEPRECATED__a1z_msgs__action__MoveEndEffector_GetResult_Request __attribute__((deprecated))
#else
# define DEPRECATED__a1z_msgs__action__MoveEndEffector_GetResult_Request __declspec(deprecated)
#endif

namespace a1z_msgs
{

namespace action
{

// message struct
template<class ContainerAllocator>
struct MoveEndEffector_GetResult_Request_
{
  using Type = MoveEndEffector_GetResult_Request_<ContainerAllocator>;

  explicit MoveEndEffector_GetResult_Request_(rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : goal_id(_init)
  {
    (void)_init;
  }

  explicit MoveEndEffector_GetResult_Request_(const ContainerAllocator & _alloc, rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : goal_id(_alloc, _init)
  {
    (void)_init;
  }

  // field types and members
  using _goal_id_type =
    unique_identifier_msgs::msg::UUID_<ContainerAllocator>;
  _goal_id_type goal_id;

  // setters for named parameter idiom
  Type & set__goal_id(
    const unique_identifier_msgs::msg::UUID_<ContainerAllocator> & _arg)
  {
    this->goal_id = _arg;
    return *this;
  }

  // constant declarations

  // pointer types
  using RawPtr =
    a1z_msgs::action::MoveEndEffector_GetResult_Request_<ContainerAllocator> *;
  using ConstRawPtr =
    const a1z_msgs::action::MoveEndEffector_GetResult_Request_<ContainerAllocator> *;
  using SharedPtr =
    std::shared_ptr<a1z_msgs::action::MoveEndEffector_GetResult_Request_<ContainerAllocator>>;
  using ConstSharedPtr =
    std::shared_ptr<a1z_msgs::action::MoveEndEffector_GetResult_Request_<ContainerAllocator> const>;

  template<typename Deleter = std::default_delete<
      a1z_msgs::action::MoveEndEffector_GetResult_Request_<ContainerAllocator>>>
  using UniquePtrWithDeleter =
    std::unique_ptr<a1z_msgs::action::MoveEndEffector_GetResult_Request_<ContainerAllocator>, Deleter>;

  using UniquePtr = UniquePtrWithDeleter<>;

  template<typename Deleter = std::default_delete<
      a1z_msgs::action::MoveEndEffector_GetResult_Request_<ContainerAllocator>>>
  using ConstUniquePtrWithDeleter =
    std::unique_ptr<a1z_msgs::action::MoveEndEffector_GetResult_Request_<ContainerAllocator> const, Deleter>;
  using ConstUniquePtr = ConstUniquePtrWithDeleter<>;

  using WeakPtr =
    std::weak_ptr<a1z_msgs::action::MoveEndEffector_GetResult_Request_<ContainerAllocator>>;
  using ConstWeakPtr =
    std::weak_ptr<a1z_msgs::action::MoveEndEffector_GetResult_Request_<ContainerAllocator> const>;

  // pointer types similar to ROS 1, use SharedPtr / ConstSharedPtr instead
  // NOTE: Can't use 'using' here because GNU C++ can't parse attributes properly
  typedef DEPRECATED__a1z_msgs__action__MoveEndEffector_GetResult_Request
    std::shared_ptr<a1z_msgs::action::MoveEndEffector_GetResult_Request_<ContainerAllocator>>
    Ptr;
  typedef DEPRECATED__a1z_msgs__action__MoveEndEffector_GetResult_Request
    std::shared_ptr<a1z_msgs::action::MoveEndEffector_GetResult_Request_<ContainerAllocator> const>
    ConstPtr;

  // comparison operators
  bool operator==(const MoveEndEffector_GetResult_Request_ & other) const
  {
    if (this->goal_id != other.goal_id) {
      return false;
    }
    return true;
  }
  bool operator!=(const MoveEndEffector_GetResult_Request_ & other) const
  {
    return !this->operator==(other);
  }
};  // struct MoveEndEffector_GetResult_Request_

// alias to use template instance with default allocator
using MoveEndEffector_GetResult_Request =
  a1z_msgs::action::MoveEndEffector_GetResult_Request_<std::allocator<void>>;

// constant definitions

}  // namespace action

}  // namespace a1z_msgs


// Include directives for member types
// Member 'result'
// already included above
// #include "a1z_msgs/action/detail/move_end_effector__struct.hpp"

#ifndef _WIN32
# define DEPRECATED__a1z_msgs__action__MoveEndEffector_GetResult_Response __attribute__((deprecated))
#else
# define DEPRECATED__a1z_msgs__action__MoveEndEffector_GetResult_Response __declspec(deprecated)
#endif

namespace a1z_msgs
{

namespace action
{

// message struct
template<class ContainerAllocator>
struct MoveEndEffector_GetResult_Response_
{
  using Type = MoveEndEffector_GetResult_Response_<ContainerAllocator>;

  explicit MoveEndEffector_GetResult_Response_(rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : result(_init)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->status = 0;
    }
  }

  explicit MoveEndEffector_GetResult_Response_(const ContainerAllocator & _alloc, rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : result(_alloc, _init)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->status = 0;
    }
  }

  // field types and members
  using _status_type =
    int8_t;
  _status_type status;
  using _result_type =
    a1z_msgs::action::MoveEndEffector_Result_<ContainerAllocator>;
  _result_type result;

  // setters for named parameter idiom
  Type & set__status(
    const int8_t & _arg)
  {
    this->status = _arg;
    return *this;
  }
  Type & set__result(
    const a1z_msgs::action::MoveEndEffector_Result_<ContainerAllocator> & _arg)
  {
    this->result = _arg;
    return *this;
  }

  // constant declarations

  // pointer types
  using RawPtr =
    a1z_msgs::action::MoveEndEffector_GetResult_Response_<ContainerAllocator> *;
  using ConstRawPtr =
    const a1z_msgs::action::MoveEndEffector_GetResult_Response_<ContainerAllocator> *;
  using SharedPtr =
    std::shared_ptr<a1z_msgs::action::MoveEndEffector_GetResult_Response_<ContainerAllocator>>;
  using ConstSharedPtr =
    std::shared_ptr<a1z_msgs::action::MoveEndEffector_GetResult_Response_<ContainerAllocator> const>;

  template<typename Deleter = std::default_delete<
      a1z_msgs::action::MoveEndEffector_GetResult_Response_<ContainerAllocator>>>
  using UniquePtrWithDeleter =
    std::unique_ptr<a1z_msgs::action::MoveEndEffector_GetResult_Response_<ContainerAllocator>, Deleter>;

  using UniquePtr = UniquePtrWithDeleter<>;

  template<typename Deleter = std::default_delete<
      a1z_msgs::action::MoveEndEffector_GetResult_Response_<ContainerAllocator>>>
  using ConstUniquePtrWithDeleter =
    std::unique_ptr<a1z_msgs::action::MoveEndEffector_GetResult_Response_<ContainerAllocator> const, Deleter>;
  using ConstUniquePtr = ConstUniquePtrWithDeleter<>;

  using WeakPtr =
    std::weak_ptr<a1z_msgs::action::MoveEndEffector_GetResult_Response_<ContainerAllocator>>;
  using ConstWeakPtr =
    std::weak_ptr<a1z_msgs::action::MoveEndEffector_GetResult_Response_<ContainerAllocator> const>;

  // pointer types similar to ROS 1, use SharedPtr / ConstSharedPtr instead
  // NOTE: Can't use 'using' here because GNU C++ can't parse attributes properly
  typedef DEPRECATED__a1z_msgs__action__MoveEndEffector_GetResult_Response
    std::shared_ptr<a1z_msgs::action::MoveEndEffector_GetResult_Response_<ContainerAllocator>>
    Ptr;
  typedef DEPRECATED__a1z_msgs__action__MoveEndEffector_GetResult_Response
    std::shared_ptr<a1z_msgs::action::MoveEndEffector_GetResult_Response_<ContainerAllocator> const>
    ConstPtr;

  // comparison operators
  bool operator==(const MoveEndEffector_GetResult_Response_ & other) const
  {
    if (this->status != other.status) {
      return false;
    }
    if (this->result != other.result) {
      return false;
    }
    return true;
  }
  bool operator!=(const MoveEndEffector_GetResult_Response_ & other) const
  {
    return !this->operator==(other);
  }
};  // struct MoveEndEffector_GetResult_Response_

// alias to use template instance with default allocator
using MoveEndEffector_GetResult_Response =
  a1z_msgs::action::MoveEndEffector_GetResult_Response_<std::allocator<void>>;

// constant definitions

}  // namespace action

}  // namespace a1z_msgs

namespace a1z_msgs
{

namespace action
{

struct MoveEndEffector_GetResult
{
  using Request = a1z_msgs::action::MoveEndEffector_GetResult_Request;
  using Response = a1z_msgs::action::MoveEndEffector_GetResult_Response;
};

}  // namespace action

}  // namespace a1z_msgs


// Include directives for member types
// Member 'goal_id'
// already included above
// #include "unique_identifier_msgs/msg/detail/uuid__struct.hpp"
// Member 'feedback'
// already included above
// #include "a1z_msgs/action/detail/move_end_effector__struct.hpp"

#ifndef _WIN32
# define DEPRECATED__a1z_msgs__action__MoveEndEffector_FeedbackMessage __attribute__((deprecated))
#else
# define DEPRECATED__a1z_msgs__action__MoveEndEffector_FeedbackMessage __declspec(deprecated)
#endif

namespace a1z_msgs
{

namespace action
{

// message struct
template<class ContainerAllocator>
struct MoveEndEffector_FeedbackMessage_
{
  using Type = MoveEndEffector_FeedbackMessage_<ContainerAllocator>;

  explicit MoveEndEffector_FeedbackMessage_(rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : goal_id(_init),
    feedback(_init)
  {
    (void)_init;
  }

  explicit MoveEndEffector_FeedbackMessage_(const ContainerAllocator & _alloc, rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : goal_id(_alloc, _init),
    feedback(_alloc, _init)
  {
    (void)_init;
  }

  // field types and members
  using _goal_id_type =
    unique_identifier_msgs::msg::UUID_<ContainerAllocator>;
  _goal_id_type goal_id;
  using _feedback_type =
    a1z_msgs::action::MoveEndEffector_Feedback_<ContainerAllocator>;
  _feedback_type feedback;

  // setters for named parameter idiom
  Type & set__goal_id(
    const unique_identifier_msgs::msg::UUID_<ContainerAllocator> & _arg)
  {
    this->goal_id = _arg;
    return *this;
  }
  Type & set__feedback(
    const a1z_msgs::action::MoveEndEffector_Feedback_<ContainerAllocator> & _arg)
  {
    this->feedback = _arg;
    return *this;
  }

  // constant declarations

  // pointer types
  using RawPtr =
    a1z_msgs::action::MoveEndEffector_FeedbackMessage_<ContainerAllocator> *;
  using ConstRawPtr =
    const a1z_msgs::action::MoveEndEffector_FeedbackMessage_<ContainerAllocator> *;
  using SharedPtr =
    std::shared_ptr<a1z_msgs::action::MoveEndEffector_FeedbackMessage_<ContainerAllocator>>;
  using ConstSharedPtr =
    std::shared_ptr<a1z_msgs::action::MoveEndEffector_FeedbackMessage_<ContainerAllocator> const>;

  template<typename Deleter = std::default_delete<
      a1z_msgs::action::MoveEndEffector_FeedbackMessage_<ContainerAllocator>>>
  using UniquePtrWithDeleter =
    std::unique_ptr<a1z_msgs::action::MoveEndEffector_FeedbackMessage_<ContainerAllocator>, Deleter>;

  using UniquePtr = UniquePtrWithDeleter<>;

  template<typename Deleter = std::default_delete<
      a1z_msgs::action::MoveEndEffector_FeedbackMessage_<ContainerAllocator>>>
  using ConstUniquePtrWithDeleter =
    std::unique_ptr<a1z_msgs::action::MoveEndEffector_FeedbackMessage_<ContainerAllocator> const, Deleter>;
  using ConstUniquePtr = ConstUniquePtrWithDeleter<>;

  using WeakPtr =
    std::weak_ptr<a1z_msgs::action::MoveEndEffector_FeedbackMessage_<ContainerAllocator>>;
  using ConstWeakPtr =
    std::weak_ptr<a1z_msgs::action::MoveEndEffector_FeedbackMessage_<ContainerAllocator> const>;

  // pointer types similar to ROS 1, use SharedPtr / ConstSharedPtr instead
  // NOTE: Can't use 'using' here because GNU C++ can't parse attributes properly
  typedef DEPRECATED__a1z_msgs__action__MoveEndEffector_FeedbackMessage
    std::shared_ptr<a1z_msgs::action::MoveEndEffector_FeedbackMessage_<ContainerAllocator>>
    Ptr;
  typedef DEPRECATED__a1z_msgs__action__MoveEndEffector_FeedbackMessage
    std::shared_ptr<a1z_msgs::action::MoveEndEffector_FeedbackMessage_<ContainerAllocator> const>
    ConstPtr;

  // comparison operators
  bool operator==(const MoveEndEffector_FeedbackMessage_ & other) const
  {
    if (this->goal_id != other.goal_id) {
      return false;
    }
    if (this->feedback != other.feedback) {
      return false;
    }
    return true;
  }
  bool operator!=(const MoveEndEffector_FeedbackMessage_ & other) const
  {
    return !this->operator==(other);
  }
};  // struct MoveEndEffector_FeedbackMessage_

// alias to use template instance with default allocator
using MoveEndEffector_FeedbackMessage =
  a1z_msgs::action::MoveEndEffector_FeedbackMessage_<std::allocator<void>>;

// constant definitions

}  // namespace action

}  // namespace a1z_msgs

#include "action_msgs/srv/cancel_goal.hpp"
#include "action_msgs/msg/goal_info.hpp"
#include "action_msgs/msg/goal_status_array.hpp"

namespace a1z_msgs
{

namespace action
{

struct MoveEndEffector
{
  /// The goal message defined in the action definition.
  using Goal = a1z_msgs::action::MoveEndEffector_Goal;
  /// The result message defined in the action definition.
  using Result = a1z_msgs::action::MoveEndEffector_Result;
  /// The feedback message defined in the action definition.
  using Feedback = a1z_msgs::action::MoveEndEffector_Feedback;

  struct Impl
  {
    /// The send_goal service using a wrapped version of the goal message as a request.
    using SendGoalService = a1z_msgs::action::MoveEndEffector_SendGoal;
    /// The get_result service using a wrapped version of the result message as a response.
    using GetResultService = a1z_msgs::action::MoveEndEffector_GetResult;
    /// The feedback message with generic fields which wraps the feedback message.
    using FeedbackMessage = a1z_msgs::action::MoveEndEffector_FeedbackMessage;

    /// The generic service to cancel a goal.
    using CancelGoalService = action_msgs::srv::CancelGoal;
    /// The generic message for the status of a goal.
    using GoalStatusMessage = action_msgs::msg::GoalStatusArray;
  };
};

typedef struct MoveEndEffector MoveEndEffector;

}  // namespace action

}  // namespace a1z_msgs

#endif  // A1Z_MSGS__ACTION__DETAIL__MOVE_END_EFFECTOR__STRUCT_HPP_
