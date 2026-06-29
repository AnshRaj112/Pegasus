import React, { useEffect } from 'react';
import { Row, Col, Flex } from 'antd';

import { useAppDispatch } from '~/redux/store';

import styles from './Profile.module.scss';
import { UserProfile } from './Profile.interface';

const mockUser: UserProfile = {
  firstName: 'Super User',
  lastName: '-',
  userName: 'superuser@onixnet.com',
  email: 'superuser@onixnet.com',
  role: 'ADMINISTRATOR',
  assignedWorkspaces: 'PELICAN',
  lastLoginTime: '2026-06-12 11:47:03',
  organization: '-',
  team: '-',
  location: '-',
  isLocal: true,
};

const Profile: React.FC = () => {
  const dispatch = useAppDispatch();
  const data = mockUser; 

  useEffect(() => {
    // dispatch({ type: 'FETCH_PROFILE_REQUEST' });
  }, [dispatch]);

  if (!data) return <div>Loading...</div>;

  return (
    <main className={`d-flex flex-column gap-4 py-4 px-3 px-md-0 ${styles.container}`}>
      
      {/* Card A (Header) */}
      <section className={styles.card}>
        <h1 className={`m-0 ${styles.headlineMd}`}>Profile</h1>
      </section>

      {/* Card B (User Details) */}
      <section className={styles.card}>
        <Flex align="center" gap="small" className="mb-4">
          <h2 className={`m-0 ${styles.headlineSm}`}>User Details</h2>
          {data.isLocal && (
            <span className={styles.badgeLocal}>LOCAL</span>
          )}
        </Flex>

        <Row gutter={[36, 30]}>
          <Col xs={24} md={12}>
            <Flex vertical gap="small">
              <label className={styles.label}>First Name</label>
              <p className={styles.value}>{data.firstName}</p>
            </Flex>
          </Col>

          <Col xs={24} md={12}>
            <Flex vertical gap="small">
              <label className={styles.label}>Last Name</label>
              <p className={styles.value}>{data.lastName}</p>
            </Flex>
          </Col>

          <Col xs={24} md={12}>
            <Flex vertical gap="small">
              <label className={styles.label}>User Name</label>
              <p className={styles.value}>{data.userName}</p>
            </Flex>
          </Col>

          <Col xs={24} md={12}>
            <Flex vertical gap="small">
              <label className={styles.label}>Email</label>
                <p className={styles.value}>{data.email}</p>
            </Flex>
          </Col>

          <Col xs={24} md={12}>
            <Flex vertical gap="small">
              <label className={styles.label}>Role</label>
              <div>
                <span className={styles.badgeRole}>
                  {data.role}
                </span>
              </div>
            </Flex>
          </Col>

          <Col xs={24} md={12}>
            <Flex vertical gap="small">
              <label className={styles.label}>Assigned Workspaces</label>
              <div>
                <span className={styles.badgeWorkspace}>
                  {data.assignedWorkspaces}
                </span>
              </div>
            </Flex>
          </Col>

          <Col xs={24} md={12}>
            <Flex vertical gap="small">
              <label className={styles.label}>Last Login Time</label>
                <p className={styles.value}>{data.lastLoginTime}</p>
            </Flex>
          </Col>

          <Col xs={24} md={12}>
            <Flex vertical gap="small">
              <label className={styles.label}>Organization</label>
              <p className={styles.value}>{data.organization}</p>
            </Flex>
          </Col>

          <Col xs={24} md={12}>
            <Flex vertical gap="small">
              <label className={styles.label}>Team</label>
              <p className={styles.value}>{data.team}</p>
            </Flex>
          </Col>

          <Col xs={24} md={12}>
            <Flex vertical gap="small">
              <label className={styles.label}>Location</label>
                <p className={styles.value}>{data.location}</p>
            </Flex>
          </Col>
        </Row>
      </section>

      {/* Card C (Password) */}
      <section className={styles.card}>
        <h2 className={`mb-4 ${styles.headlineSm}`}>Password</h2>
        <div>
          <button className={`btn ${styles.btnPrimaryOutline}`}>
            {/* <span className="material-symbols-outlined fs-6">lock_reset</span> */}
            Reset Password
          </button>
        </div>
      </section>

      <footer className={styles.footer}>
        © 2026 Pegasus Systems • Administrative Profile Management Interface
      </footer>
    </main>
  );
};

export default Profile;