
#[cfg(feature = "serde")]
use serde::{Deserialize, Serialize};



// Corresponds to a1z_msgs__action__MoveEndEffector_Goal

// This struct is not documented.
#[allow(missing_docs)]

#[allow(non_camel_case_types)]
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct MoveEndEffector_Goal {

    // This member is not documented.
    #[allow(missing_docs)]
    pub goal_pose: geometry_msgs::msg::PoseStamped,


    // This member is not documented.
    #[allow(missing_docs)]
    pub end_effector_frame: std::string::String,


    // This member is not documented.
    #[allow(missing_docs)]
    pub command_gripper: bool,


    // This member is not documented.
    #[allow(missing_docs)]
    pub gripper_opening: f32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub speed: f32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub position_tolerance_m: f32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub orientation_tolerance_rad: f32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub joint_margin_rad: f32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub max_joint_step_rad: f32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub min_target_z_m: f32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub max_target_z_m: f32,

}



impl Default for MoveEndEffector_Goal {
  fn default() -> Self {
    <Self as rosidl_runtime_rs::Message>::from_rmw_message(super::action::rmw::MoveEndEffector_Goal::default())
  }
}

impl rosidl_runtime_rs::Message for MoveEndEffector_Goal {
  type RmwMsg = super::action::rmw::MoveEndEffector_Goal;

  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> {
    match msg_cow {
      std::borrow::Cow::Owned(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        goal_pose: geometry_msgs::msg::PoseStamped::into_rmw_message(std::borrow::Cow::Owned(msg.goal_pose)).into_owned(),
        end_effector_frame: msg.end_effector_frame.as_str().into(),
        command_gripper: msg.command_gripper,
        gripper_opening: msg.gripper_opening,
        speed: msg.speed,
        position_tolerance_m: msg.position_tolerance_m,
        orientation_tolerance_rad: msg.orientation_tolerance_rad,
        joint_margin_rad: msg.joint_margin_rad,
        max_joint_step_rad: msg.max_joint_step_rad,
        min_target_z_m: msg.min_target_z_m,
        max_target_z_m: msg.max_target_z_m,
      }),
      std::borrow::Cow::Borrowed(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        goal_pose: geometry_msgs::msg::PoseStamped::into_rmw_message(std::borrow::Cow::Borrowed(&msg.goal_pose)).into_owned(),
        end_effector_frame: msg.end_effector_frame.as_str().into(),
      command_gripper: msg.command_gripper,
      gripper_opening: msg.gripper_opening,
      speed: msg.speed,
      position_tolerance_m: msg.position_tolerance_m,
      orientation_tolerance_rad: msg.orientation_tolerance_rad,
      joint_margin_rad: msg.joint_margin_rad,
      max_joint_step_rad: msg.max_joint_step_rad,
      min_target_z_m: msg.min_target_z_m,
      max_target_z_m: msg.max_target_z_m,
      })
    }
  }

  fn from_rmw_message(msg: Self::RmwMsg) -> Self {
    Self {
      goal_pose: geometry_msgs::msg::PoseStamped::from_rmw_message(msg.goal_pose),
      end_effector_frame: msg.end_effector_frame.to_string(),
      command_gripper: msg.command_gripper,
      gripper_opening: msg.gripper_opening,
      speed: msg.speed,
      position_tolerance_m: msg.position_tolerance_m,
      orientation_tolerance_rad: msg.orientation_tolerance_rad,
      joint_margin_rad: msg.joint_margin_rad,
      max_joint_step_rad: msg.max_joint_step_rad,
      min_target_z_m: msg.min_target_z_m,
      max_target_z_m: msg.max_target_z_m,
    }
  }
}


// Corresponds to a1z_msgs__action__MoveEndEffector_Result

// This struct is not documented.
#[allow(missing_docs)]

#[allow(non_camel_case_types)]
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct MoveEndEffector_Result {

    // This member is not documented.
    #[allow(missing_docs)]
    pub success: bool,


    // This member is not documented.
    #[allow(missing_docs)]
    pub status: std::string::String,


    // This member is not documented.
    #[allow(missing_docs)]
    pub failure_reason: std::string::String,


    // This member is not documented.
    #[allow(missing_docs)]
    pub final_joint_positions_rad: Vec<f64>,


    // This member is not documented.
    #[allow(missing_docs)]
    pub final_pose: geometry_msgs::msg::PoseStamped,


    // This member is not documented.
    #[allow(missing_docs)]
    pub final_gripper_opening: f32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub ik_converged: bool,


    // This member is not documented.
    #[allow(missing_docs)]
    pub position_error_m: f32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub orientation_error_rad: f32,

}



impl Default for MoveEndEffector_Result {
  fn default() -> Self {
    <Self as rosidl_runtime_rs::Message>::from_rmw_message(super::action::rmw::MoveEndEffector_Result::default())
  }
}

impl rosidl_runtime_rs::Message for MoveEndEffector_Result {
  type RmwMsg = super::action::rmw::MoveEndEffector_Result;

  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> {
    match msg_cow {
      std::borrow::Cow::Owned(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        success: msg.success,
        status: msg.status.as_str().into(),
        failure_reason: msg.failure_reason.as_str().into(),
        final_joint_positions_rad: msg.final_joint_positions_rad.into(),
        final_pose: geometry_msgs::msg::PoseStamped::into_rmw_message(std::borrow::Cow::Owned(msg.final_pose)).into_owned(),
        final_gripper_opening: msg.final_gripper_opening,
        ik_converged: msg.ik_converged,
        position_error_m: msg.position_error_m,
        orientation_error_rad: msg.orientation_error_rad,
      }),
      std::borrow::Cow::Borrowed(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
      success: msg.success,
        status: msg.status.as_str().into(),
        failure_reason: msg.failure_reason.as_str().into(),
        final_joint_positions_rad: msg.final_joint_positions_rad.as_slice().into(),
        final_pose: geometry_msgs::msg::PoseStamped::into_rmw_message(std::borrow::Cow::Borrowed(&msg.final_pose)).into_owned(),
      final_gripper_opening: msg.final_gripper_opening,
      ik_converged: msg.ik_converged,
      position_error_m: msg.position_error_m,
      orientation_error_rad: msg.orientation_error_rad,
      })
    }
  }

  fn from_rmw_message(msg: Self::RmwMsg) -> Self {
    Self {
      success: msg.success,
      status: msg.status.to_string(),
      failure_reason: msg.failure_reason.to_string(),
      final_joint_positions_rad: msg.final_joint_positions_rad
          .into_iter()
          .collect(),
      final_pose: geometry_msgs::msg::PoseStamped::from_rmw_message(msg.final_pose),
      final_gripper_opening: msg.final_gripper_opening,
      ik_converged: msg.ik_converged,
      position_error_m: msg.position_error_m,
      orientation_error_rad: msg.orientation_error_rad,
    }
  }
}


// Corresponds to a1z_msgs__action__MoveEndEffector_Feedback

// This struct is not documented.
#[allow(missing_docs)]

#[allow(non_camel_case_types)]
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct MoveEndEffector_Feedback {

    // This member is not documented.
    #[allow(missing_docs)]
    pub stage: std::string::String,


    // This member is not documented.
    #[allow(missing_docs)]
    pub message: std::string::String,

}



impl Default for MoveEndEffector_Feedback {
  fn default() -> Self {
    <Self as rosidl_runtime_rs::Message>::from_rmw_message(super::action::rmw::MoveEndEffector_Feedback::default())
  }
}

impl rosidl_runtime_rs::Message for MoveEndEffector_Feedback {
  type RmwMsg = super::action::rmw::MoveEndEffector_Feedback;

  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> {
    match msg_cow {
      std::borrow::Cow::Owned(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        stage: msg.stage.as_str().into(),
        message: msg.message.as_str().into(),
      }),
      std::borrow::Cow::Borrowed(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        stage: msg.stage.as_str().into(),
        message: msg.message.as_str().into(),
      })
    }
  }

  fn from_rmw_message(msg: Self::RmwMsg) -> Self {
    Self {
      stage: msg.stage.to_string(),
      message: msg.message.to_string(),
    }
  }
}


// Corresponds to a1z_msgs__action__MoveEndEffector_FeedbackMessage

// This struct is not documented.
#[allow(missing_docs)]

#[allow(non_camel_case_types)]
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct MoveEndEffector_FeedbackMessage {

    // This member is not documented.
    #[allow(missing_docs)]
    pub goal_id: unique_identifier_msgs::msg::UUID,


    // This member is not documented.
    #[allow(missing_docs)]
    pub feedback: super::action::MoveEndEffector_Feedback,

}



impl Default for MoveEndEffector_FeedbackMessage {
  fn default() -> Self {
    <Self as rosidl_runtime_rs::Message>::from_rmw_message(super::action::rmw::MoveEndEffector_FeedbackMessage::default())
  }
}

impl rosidl_runtime_rs::Message for MoveEndEffector_FeedbackMessage {
  type RmwMsg = super::action::rmw::MoveEndEffector_FeedbackMessage;

  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> {
    match msg_cow {
      std::borrow::Cow::Owned(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        goal_id: unique_identifier_msgs::msg::UUID::into_rmw_message(std::borrow::Cow::Owned(msg.goal_id)).into_owned(),
        feedback: super::action::MoveEndEffector_Feedback::into_rmw_message(std::borrow::Cow::Owned(msg.feedback)).into_owned(),
      }),
      std::borrow::Cow::Borrowed(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        goal_id: unique_identifier_msgs::msg::UUID::into_rmw_message(std::borrow::Cow::Borrowed(&msg.goal_id)).into_owned(),
        feedback: super::action::MoveEndEffector_Feedback::into_rmw_message(std::borrow::Cow::Borrowed(&msg.feedback)).into_owned(),
      })
    }
  }

  fn from_rmw_message(msg: Self::RmwMsg) -> Self {
    Self {
      goal_id: unique_identifier_msgs::msg::UUID::from_rmw_message(msg.goal_id),
      feedback: super::action::MoveEndEffector_Feedback::from_rmw_message(msg.feedback),
    }
  }
}






// Corresponds to a1z_msgs__action__MoveEndEffector_SendGoal_Request

// This struct is not documented.
#[allow(missing_docs)]

#[allow(non_camel_case_types)]
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct MoveEndEffector_SendGoal_Request {

    // This member is not documented.
    #[allow(missing_docs)]
    pub goal_id: unique_identifier_msgs::msg::UUID,


    // This member is not documented.
    #[allow(missing_docs)]
    pub goal: super::action::MoveEndEffector_Goal,

}



impl Default for MoveEndEffector_SendGoal_Request {
  fn default() -> Self {
    <Self as rosidl_runtime_rs::Message>::from_rmw_message(super::action::rmw::MoveEndEffector_SendGoal_Request::default())
  }
}

impl rosidl_runtime_rs::Message for MoveEndEffector_SendGoal_Request {
  type RmwMsg = super::action::rmw::MoveEndEffector_SendGoal_Request;

  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> {
    match msg_cow {
      std::borrow::Cow::Owned(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        goal_id: unique_identifier_msgs::msg::UUID::into_rmw_message(std::borrow::Cow::Owned(msg.goal_id)).into_owned(),
        goal: super::action::MoveEndEffector_Goal::into_rmw_message(std::borrow::Cow::Owned(msg.goal)).into_owned(),
      }),
      std::borrow::Cow::Borrowed(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        goal_id: unique_identifier_msgs::msg::UUID::into_rmw_message(std::borrow::Cow::Borrowed(&msg.goal_id)).into_owned(),
        goal: super::action::MoveEndEffector_Goal::into_rmw_message(std::borrow::Cow::Borrowed(&msg.goal)).into_owned(),
      })
    }
  }

  fn from_rmw_message(msg: Self::RmwMsg) -> Self {
    Self {
      goal_id: unique_identifier_msgs::msg::UUID::from_rmw_message(msg.goal_id),
      goal: super::action::MoveEndEffector_Goal::from_rmw_message(msg.goal),
    }
  }
}


// Corresponds to a1z_msgs__action__MoveEndEffector_SendGoal_Response

// This struct is not documented.
#[allow(missing_docs)]

#[allow(non_camel_case_types)]
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct MoveEndEffector_SendGoal_Response {

    // This member is not documented.
    #[allow(missing_docs)]
    pub accepted: bool,


    // This member is not documented.
    #[allow(missing_docs)]
    pub stamp: builtin_interfaces::msg::Time,

}



impl Default for MoveEndEffector_SendGoal_Response {
  fn default() -> Self {
    <Self as rosidl_runtime_rs::Message>::from_rmw_message(super::action::rmw::MoveEndEffector_SendGoal_Response::default())
  }
}

impl rosidl_runtime_rs::Message for MoveEndEffector_SendGoal_Response {
  type RmwMsg = super::action::rmw::MoveEndEffector_SendGoal_Response;

  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> {
    match msg_cow {
      std::borrow::Cow::Owned(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        accepted: msg.accepted,
        stamp: builtin_interfaces::msg::Time::into_rmw_message(std::borrow::Cow::Owned(msg.stamp)).into_owned(),
      }),
      std::borrow::Cow::Borrowed(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
      accepted: msg.accepted,
        stamp: builtin_interfaces::msg::Time::into_rmw_message(std::borrow::Cow::Borrowed(&msg.stamp)).into_owned(),
      })
    }
  }

  fn from_rmw_message(msg: Self::RmwMsg) -> Self {
    Self {
      accepted: msg.accepted,
      stamp: builtin_interfaces::msg::Time::from_rmw_message(msg.stamp),
    }
  }
}


// Corresponds to a1z_msgs__action__MoveEndEffector_GetResult_Request

// This struct is not documented.
#[allow(missing_docs)]

#[allow(non_camel_case_types)]
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct MoveEndEffector_GetResult_Request {

    // This member is not documented.
    #[allow(missing_docs)]
    pub goal_id: unique_identifier_msgs::msg::UUID,

}



impl Default for MoveEndEffector_GetResult_Request {
  fn default() -> Self {
    <Self as rosidl_runtime_rs::Message>::from_rmw_message(super::action::rmw::MoveEndEffector_GetResult_Request::default())
  }
}

impl rosidl_runtime_rs::Message for MoveEndEffector_GetResult_Request {
  type RmwMsg = super::action::rmw::MoveEndEffector_GetResult_Request;

  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> {
    match msg_cow {
      std::borrow::Cow::Owned(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        goal_id: unique_identifier_msgs::msg::UUID::into_rmw_message(std::borrow::Cow::Owned(msg.goal_id)).into_owned(),
      }),
      std::borrow::Cow::Borrowed(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        goal_id: unique_identifier_msgs::msg::UUID::into_rmw_message(std::borrow::Cow::Borrowed(&msg.goal_id)).into_owned(),
      })
    }
  }

  fn from_rmw_message(msg: Self::RmwMsg) -> Self {
    Self {
      goal_id: unique_identifier_msgs::msg::UUID::from_rmw_message(msg.goal_id),
    }
  }
}


// Corresponds to a1z_msgs__action__MoveEndEffector_GetResult_Response

// This struct is not documented.
#[allow(missing_docs)]

#[allow(non_camel_case_types)]
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct MoveEndEffector_GetResult_Response {

    // This member is not documented.
    #[allow(missing_docs)]
    pub status: i8,


    // This member is not documented.
    #[allow(missing_docs)]
    pub result: super::action::MoveEndEffector_Result,

}



impl Default for MoveEndEffector_GetResult_Response {
  fn default() -> Self {
    <Self as rosidl_runtime_rs::Message>::from_rmw_message(super::action::rmw::MoveEndEffector_GetResult_Response::default())
  }
}

impl rosidl_runtime_rs::Message for MoveEndEffector_GetResult_Response {
  type RmwMsg = super::action::rmw::MoveEndEffector_GetResult_Response;

  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> {
    match msg_cow {
      std::borrow::Cow::Owned(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        status: msg.status,
        result: super::action::MoveEndEffector_Result::into_rmw_message(std::borrow::Cow::Owned(msg.result)).into_owned(),
      }),
      std::borrow::Cow::Borrowed(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
      status: msg.status,
        result: super::action::MoveEndEffector_Result::into_rmw_message(std::borrow::Cow::Borrowed(&msg.result)).into_owned(),
      })
    }
  }

  fn from_rmw_message(msg: Self::RmwMsg) -> Self {
    Self {
      status: msg.status,
      result: super::action::MoveEndEffector_Result::from_rmw_message(msg.result),
    }
  }
}






#[link(name = "a1z_msgs__rosidl_typesupport_c")]
extern "C" {
    fn rosidl_typesupport_c__get_service_type_support_handle__a1z_msgs__action__MoveEndEffector_SendGoal() -> *const std::ffi::c_void;
}

// Corresponds to a1z_msgs__action__MoveEndEffector_SendGoal
#[allow(missing_docs, non_camel_case_types)]
pub struct MoveEndEffector_SendGoal;

impl rosidl_runtime_rs::Service for MoveEndEffector_SendGoal {
    type Request = MoveEndEffector_SendGoal_Request;
    type Response = MoveEndEffector_SendGoal_Response;

    fn get_type_support() -> *const std::ffi::c_void {
        // SAFETY: No preconditions for this function.
        unsafe { rosidl_typesupport_c__get_service_type_support_handle__a1z_msgs__action__MoveEndEffector_SendGoal() }
    }
}




#[link(name = "a1z_msgs__rosidl_typesupport_c")]
extern "C" {
    fn rosidl_typesupport_c__get_service_type_support_handle__a1z_msgs__action__MoveEndEffector_GetResult() -> *const std::ffi::c_void;
}

// Corresponds to a1z_msgs__action__MoveEndEffector_GetResult
#[allow(missing_docs, non_camel_case_types)]
pub struct MoveEndEffector_GetResult;

impl rosidl_runtime_rs::Service for MoveEndEffector_GetResult {
    type Request = MoveEndEffector_GetResult_Request;
    type Response = MoveEndEffector_GetResult_Response;

    fn get_type_support() -> *const std::ffi::c_void {
        // SAFETY: No preconditions for this function.
        unsafe { rosidl_typesupport_c__get_service_type_support_handle__a1z_msgs__action__MoveEndEffector_GetResult() }
    }
}






#[link(name = "a1z_msgs__rosidl_typesupport_c")]
extern "C" {
    fn rosidl_typesupport_c__get_action_type_support_handle__a1z_msgs__action__MoveEndEffector() -> *const std::ffi::c_void;
}

// Corresponds to a1z_msgs__action__MoveEndEffector
#[allow(missing_docs, non_camel_case_types)]
pub struct MoveEndEffector;

impl rosidl_runtime_rs::Action for MoveEndEffector {
  // --- Associated types for client library users ---
  /// The goal message defined in the action definition.
  type Goal = MoveEndEffector_Goal;

  /// The result message defined in the action definition.
  type Result = MoveEndEffector_Result;

  /// The feedback message defined in the action definition.
  type Feedback = MoveEndEffector_Feedback;

  // --- Associated types for client library implementation ---
  /// The feedback message with generic fields which wraps the feedback message.
  type FeedbackMessage = super::action::MoveEndEffector_FeedbackMessage;

  /// The send_goal service using a wrapped version of the goal message as a request.
  type SendGoalService = super::action::MoveEndEffector_SendGoal;

  /// The generic service to cancel a goal.
  type CancelGoalService = action_msgs::srv::rmw::CancelGoal;

  /// The get_result service using a wrapped version of the result message as a response.
  type GetResultService = super::action::MoveEndEffector_GetResult;

  // --- Methods for client library implementation ---
  fn get_type_support() -> *const std::ffi::c_void {
    // SAFETY: No preconditions for this function.
    unsafe { rosidl_typesupport_c__get_action_type_support_handle__a1z_msgs__action__MoveEndEffector() }
  }

  fn create_goal_request(
    goal_id: &[u8; 16],
    goal: super::action::rmw::MoveEndEffector_Goal,
  ) -> super::action::rmw::MoveEndEffector_SendGoal_Request {
   super::action::rmw::MoveEndEffector_SendGoal_Request {
      goal_id: unique_identifier_msgs::msg::rmw::UUID { uuid: *goal_id },
      goal,
    }
  }

  fn split_goal_request(
    request: super::action::rmw::MoveEndEffector_SendGoal_Request,
  ) -> (
    [u8; 16],
   super::action::rmw::MoveEndEffector_Goal,
  ) {
    (request.goal_id.uuid, request.goal)
  }

  fn create_goal_response(
    accepted: bool,
    stamp: (i32, u32),
  ) -> super::action::rmw::MoveEndEffector_SendGoal_Response {
   super::action::rmw::MoveEndEffector_SendGoal_Response {
      accepted,
      stamp: builtin_interfaces::msg::rmw::Time {
        sec: stamp.0,
        nanosec: stamp.1,
      },
    }
  }

  fn get_goal_response_accepted(
    response: &super::action::rmw::MoveEndEffector_SendGoal_Response,
  ) -> bool {
    response.accepted
  }

  fn get_goal_response_stamp(
    response: &super::action::rmw::MoveEndEffector_SendGoal_Response,
  ) -> (i32, u32) {
    (response.stamp.sec, response.stamp.nanosec)
  }

  fn create_feedback_message(
    goal_id: &[u8; 16],
    feedback: super::action::rmw::MoveEndEffector_Feedback,
  ) -> super::action::rmw::MoveEndEffector_FeedbackMessage {
    let mut message = super::action::rmw::MoveEndEffector_FeedbackMessage::default();
    message.goal_id.uuid = *goal_id;
    message.feedback = feedback;
    message
  }

  fn split_feedback_message(
    feedback: super::action::rmw::MoveEndEffector_FeedbackMessage,
  ) -> (
    [u8; 16],
   super::action::rmw::MoveEndEffector_Feedback,
  ) {
    (feedback.goal_id.uuid, feedback.feedback)
  }

  fn create_result_request(
    goal_id: &[u8; 16],
  ) -> super::action::rmw::MoveEndEffector_GetResult_Request {
   super::action::rmw::MoveEndEffector_GetResult_Request {
      goal_id: unique_identifier_msgs::msg::rmw::UUID { uuid: *goal_id },
    }
  }

  fn get_result_request_uuid(
    request: &super::action::rmw::MoveEndEffector_GetResult_Request,
  ) -> &[u8; 16] {
    &request.goal_id.uuid
  }

  fn create_result_response(
    status: i8,
    result: super::action::rmw::MoveEndEffector_Result,
  ) -> super::action::rmw::MoveEndEffector_GetResult_Response {
   super::action::rmw::MoveEndEffector_GetResult_Response {
      status,
      result,
    }
  }

  fn split_result_response(
    response: super::action::rmw::MoveEndEffector_GetResult_Response
  ) -> (
    i8,
   super::action::rmw::MoveEndEffector_Result,
  ) {
    (response.status, response.result)
  }
}


