import { Skeleton } from 'antd';
import { useAppSelector } from '~/redux/store';
import styles from '../Test.module.scss';

const ActiveView = () => {
  const { data, isFetching } = useAppSelector((state) => state.test.activeTests);

  if (isFetching) {
    return <div className="p-4"><Skeleton active paragraph={{ rows: 5 }} /></div>;
  }

  if (!data || data.length === 0) {
    return <div className="p-4 text-center text-muted">No active tests found.</div>;
  }

  return (
    <div>
      {data.map((test) => (
        <div key={test.id} className={`d-flex justify-content-between align-items-center ${styles.listRow}`}>
          <div className="d-flex align-items-center col-4">
            <span className="me-2 text-secondary">⊟</span>
            <div>
              <div className="fw-bold">{test.title}</div>
              <div className="text-muted small">{test.subtitle}</div>
            </div>
          </div>
          
          <div className="col-4 text-muted small d-flex align-items-center">
            <span className="me-2">↺</span> {test.schedule}
          </div>
          
          <div className="col-4 d-flex justify-content-end align-items-center">
            <div className={`d-flex align-items-center ${styles.statusBadge}`}>
              <span className="me-2">↻</span> {test.nextRun}
              <span className={`${styles.typeIcon} ${test.type === 'F' ? styles['typeIcon--red'] : ''}`}>{test.type}</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

export default ActiveView;